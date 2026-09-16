//! CAP-01 native request/response harness.
//!
//! The protocol is newline-delimited JSON. No third-party crates are used so
//! the measured binary has no serialization framework hidden in its hot path.

use std::io::{self, BufRead, Write};
use std::time::Instant;

fn json_string(input: &str, key: &str) -> Option<String> {
    let marker = format!("\"{}\":", key);
    let start = input.find(&marker)? + marker.len();
    let bytes = input.as_bytes();
    let mut pos = start;
    while pos < bytes.len() && bytes[pos].is_ascii_whitespace() {
        pos += 1;
    }
    if bytes.get(pos) != Some(&b'"') {
        return None;
    }
    pos += 1;
    let mut value = String::new();
    while pos < bytes.len() {
        match bytes[pos] {
            b'"' => return Some(value),
            b'\\' => {
                pos += 1;
                match *bytes.get(pos)? {
                    b'"' => value.push('"'),
                    b'\\' => value.push('\\'),
                    b'/' => value.push('/'),
                    b'b' => value.push('\u{0008}'),
                    b'f' => value.push('\u{000c}'),
                    b'n' => value.push('\n'),
                    b'r' => value.push('\r'),
                    b't' => value.push('\t'),
                    b'u' => {
                        let end = pos.checked_add(5)?;
                        let high = u16::from_str_radix(input.get(pos + 1..end)?, 16).ok()?;
                        if (0xd800..=0xdbff).contains(&high) {
                            if input.get(end..end + 2)? != "\\u" {
                                return None;
                            }
                            let low_end = end.checked_add(6)?;
                            let low =
                                u16::from_str_radix(input.get(end + 2..low_end)?, 16).ok()?;
                            if !(0xdc00..=0xdfff).contains(&low) {
                                return None;
                            }
                            let scalar = 0x10000
                                + (((high as u32) - 0xd800) << 10)
                                + ((low as u32) - 0xdc00);
                            value.push(char::from_u32(scalar)?);
                            pos = low_end - 1;
                        } else {
                            value.push(char::from_u32(high as u32)?);
                            pos = end - 1;
                        }
                    }
                    _ => return None,
                }
            }
            byte if byte.is_ascii() => value.push(byte as char),
            _ => return None,
        }
        pos += 1;
    }
    None
}

fn json_u64(input: &str, key: &str) -> Option<u64> {
    let marker = format!("\"{}\":", key);
    let start = input.find(&marker)? + marker.len();
    let tail = input[start..].trim_start();
    let end = tail
        .find(|ch: char| !ch.is_ascii_digit())
        .unwrap_or(tail.len());
    tail[..end].parse().ok()
}

fn json_escape(value: &str) -> String {
    let mut result = String::with_capacity(value.len() + 2);
    for ch in value.chars() {
        match ch {
            '"' => result.push_str("\\\""),
            '\\' => result.push_str("\\\\"),
            '\n' => result.push_str("\\n"),
            '\r' => result.push_str("\\r"),
            '\t' => result.push_str("\\t"),
            ch if ch.is_control() => result.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => result.push(ch),
        }
    }
    result
}

#[cfg(unix)]
fn process_cpu_ns() -> u64 {
    #[repr(C)]
    struct Timespec {
        tv_sec: i64,
        tv_nsec: i64,
    }
    unsafe extern "C" {
        fn clock_gettime(clock_id: i32, time: *mut Timespec) -> i32;
    }
    const CLOCK_PROCESS_CPUTIME_ID: i32 = 2;
    let mut value = Timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    let status = unsafe { clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &mut value) };
    if status == 0 {
        (value.tv_sec as u64)
            .saturating_mul(1_000_000_000)
            .saturating_add(value.tv_nsec as u64)
    } else {
        0
    }
}

#[cfg(windows)]
fn process_cpu_ns() -> u64 {
    #[repr(C)]
    struct FileTime {
        low: u32,
        high: u32,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetCurrentProcess() -> *mut core::ffi::c_void;
        fn GetProcessTimes(
            process: *mut core::ffi::c_void,
            creation: *mut FileTime,
            exit: *mut FileTime,
            kernel: *mut FileTime,
            user: *mut FileTime,
        ) -> i32;
    }
    fn ticks(value: &FileTime) -> u64 {
        ((value.high as u64) << 32) | value.low as u64
    }
    let mut creation = FileTime { low: 0, high: 0 };
    let mut exit = FileTime { low: 0, high: 0 };
    let mut kernel = FileTime { low: 0, high: 0 };
    let mut user = FileTime { low: 0, high: 0 };
    let ok = unsafe {
        GetProcessTimes(
            GetCurrentProcess(),
            &mut creation,
            &mut exit,
            &mut kernel,
            &mut user,
        )
    };
    if ok == 0 {
        0
    } else {
        ticks(&kernel).saturating_add(ticks(&user)).saturating_mul(100)
    }
}

#[cfg(not(any(unix, windows)))]
fn process_cpu_ns() -> u64 {
    0
}

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut stdout = io::BufWriter::new(io::stdout().lock());
    for line in stdin.lock().lines() {
        let line = line?;
        let op = json_string(&line, "op").unwrap_or_default();
        if op == "shutdown" {
            break;
        }
        if op == "ping" {
            writeln!(stdout, "{{\"ok\":true,\"protocol\":\"cap01_v1\"}}")?;
            stdout.flush()?;
            continue;
        }
        if op != "candidate" {
            writeln!(stdout, "{{\"ok\":false,\"error\":\"unsupported operation\"}}")?;
            stdout.flush()?;
            continue;
        }

        let wall_start = Instant::now();
        let cpu_start = process_cpu_ns();
        let candidate_id = json_string(&line, "candidate_id").unwrap_or_default();
        let candidate_sha = json_string(&line, "candidate_sha256").unwrap_or_default();
        let sequence = json_u64(&line, "sequence_index").unwrap_or(0);
        let cpu_ns = process_cpu_ns().saturating_sub(cpu_start);
        let wall_ns = wall_start.elapsed().as_nanos().min(u64::MAX as u128) as u64;
        writeln!(
            stdout,
            "{{\"candidate_id\":\"{}\",\"candidate_sha256\":\"{}\",\
             \"harness_cpu_ns\":{},\"harness_wall_ns\":{},\"ok\":true,\
             \"sequence_index\":{},\"timer_scope\":\"harness_process\"}}",
            json_escape(&candidate_id),
            json_escape(&candidate_sha),
            cpu_ns,
            wall_ns,
            sequence
        )?;
        stdout.flush()?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{json_escape, json_string, json_u64};

    #[test]
    fn extracts_string_and_u64_fields() {
        let line = r#"{"op":"candidate","candidate_id":"c1","candidate_sha256":"ab","sequence_index":7}"#;
        assert_eq!(json_string(line, "op").as_deref(), Some("candidate"));
        assert_eq!(json_string(line, "candidate_id").as_deref(), Some("c1"));
        assert_eq!(json_u64(line, "sequence_index"), Some(7));
    }

    #[test]
    fn escapes_control_and_quote_characters() {
        assert_eq!(json_escape("a\"b\\c\n"), r#"a\"b\\c\n"#);
    }

    #[test]
    fn large_content_field_is_not_required_for_id_extract() {
        // Anti-leak smoke: a huge content blob must not prevent id/sha extract,
        // and must not be treated as part of the echoed identity fields.
        let content = "X".repeat(256 * 1024);
        let sha = "f".repeat(64);
        let line = format!(
            r#"{{"op":"candidate","content":"{content}","candidate_id":"big","candidate_sha256":"{sha}","sequence_index":1}}"#
        );
        assert_eq!(json_string(&line, "candidate_id").as_deref(), Some("big"));
        assert_eq!(
            json_string(&line, "content").as_deref().map(|s| s.len()),
            Some(content.len())
        );
        let id = json_string(&line, "candidate_id").unwrap();
        assert!(!id.contains('X'));
        assert_eq!(id, "big");
    }
}
