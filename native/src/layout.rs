use std::collections::HashMap;

use crate::model::{RectF, WindowInfo};

pub fn grid(keys: &[isize]) -> HashMap<isize, RectF> {
    if keys.is_empty() {
        return HashMap::new();
    }
    let columns = (keys.len() as f32).sqrt().ceil() as usize;
    let rows = keys.len().div_ceil(columns);
    let gap = 0.025;
    let cell_width = (1.0 - gap * (columns as f32 + 1.0)) / columns as f32;
    let cell_height = (1.0 - gap * (rows as f32 + 1.0)) / rows as f32;
    keys.iter()
        .enumerate()
        .map(|(index, hwnd)| {
            (
                *hwnd,
                RectF {
                    x: gap + (index % columns) as f32 * (cell_width + gap),
                    y: gap + (index / columns) as f32 * (cell_height + gap),
                    width: cell_width,
                    height: cell_height,
                },
            )
        })
        .collect()
}

pub fn strip(keys: &[isize], vertical: bool) -> HashMap<isize, RectF> {
    if keys.is_empty() {
        return HashMap::new();
    }
    let gap = 0.025;
    let size = (1.0 - gap * (keys.len() as f32 + 1.0)) / keys.len() as f32;
    keys.iter()
        .enumerate()
        .map(|(index, hwnd)| {
            let rect = if vertical {
                RectF {
                    x: gap,
                    y: gap + index as f32 * (size + gap),
                    width: 1.0 - gap * 2.0,
                    height: size,
                }
            } else {
                RectF {
                    x: gap + index as f32 * (size + gap),
                    y: gap,
                    width: size,
                    height: 1.0 - gap * 2.0,
                }
            };
            (*hwnd, rect)
        })
        .collect()
}

pub fn source_relative(windows: &[WindowInfo]) -> HashMap<isize, RectF> {
    if windows.is_empty() {
        return HashMap::new();
    }
    let left = windows.iter().map(|item| item.rect[0]).min().unwrap_or(0);
    let top = windows.iter().map(|item| item.rect[1]).min().unwrap_or(0);
    let right = windows.iter().map(|item| item.rect[2]).max().unwrap_or(1);
    let bottom = windows.iter().map(|item| item.rect[3]).max().unwrap_or(1);
    let width = (right - left).max(1) as f32;
    let height = (bottom - top).max(1) as f32;
    let padding = 0.025;
    let usable = 1.0 - padding * 2.0;
    windows
        .iter()
        .map(|item| {
            (
                item.hwnd,
                RectF {
                    x: padding + (item.rect[0] - left) as f32 / width * usable,
                    y: padding + (item.rect[1] - top) as f32 / height * usable,
                    width: ((item.rect[2] - item.rect[0]) as f32 / width * usable).max(0.08),
                    height: ((item.rect[3] - item.rect[1]) as f32 / height * usable).max(0.08),
                }
                .normalized(),
            )
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grid_contains_every_key() {
        let result = grid(&[1, 2, 3]);
        assert_eq!(result.len(), 3);
        assert!(
            result
                .values()
                .all(|rect| rect.width > 0.0 && rect.height > 0.0)
        );
    }

    #[test]
    fn normalization_keeps_rect_inside_canvas() {
        let rect = RectF {
            x: -1.0,
            y: 0.9,
            width: 2.0,
            height: 0.5,
        }
        .normalized();
        assert_eq!(rect.x, 0.0);
        assert!(rect.y + rect.height <= 1.0);
        assert_eq!(rect.width, 1.0);
    }
}
