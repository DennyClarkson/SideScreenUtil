use crate::model::{AppSettings, FilterStyle, FrameData};

const MAX_CACHED_PIXELS: f64 = 1_000_000.0;
const MAX_CACHED_DIMENSION: f64 = 1600.0;

pub fn compact_and_filter(
    raw: &[u8],
    width: u32,
    height: u32,
    row_pitch: u32,
    settings: &AppSettings,
    elapsed_seconds: f64,
) -> FrameData {
    let (target_width, target_height) =
        compact_size(width, height, settings.limit_capture_resolution);
    let mut pixels = vec![0_u8; target_width as usize * target_height as usize * 4];
    if target_width == width && target_height == height && width > 0 && height > 0 {
        let row_bytes = width as usize * 4;
        let packed_bytes = row_bytes * height as usize;
        if row_pitch as usize == row_bytes && raw.len() >= packed_bytes {
            pixels.copy_from_slice(&raw[..packed_bytes]);
        } else {
            for y in 0..height as usize {
                let source_start = y * row_pitch as usize;
                let target_start = y * row_bytes;
                if source_start + row_bytes <= raw.len() {
                    pixels[target_start..target_start + row_bytes]
                        .copy_from_slice(&raw[source_start..source_start + row_bytes]);
                }
            }
        }
    } else {
        for target_y in 0..target_height {
            let source_y = target_y as u64 * height as u64 / target_height as u64;
            for target_x in 0..target_width {
                let source_x = target_x as u64 * width as u64 / target_width as u64;
                let source_index = source_y as usize * row_pitch as usize + source_x as usize * 4;
                let target_index =
                    (target_y as usize * target_width as usize + target_x as usize) * 4;
                if source_index + 4 <= raw.len() {
                    pixels[target_index..target_index + 4]
                        .copy_from_slice(&raw[source_index..source_index + 4]);
                }
            }
        }
    }
    apply_filter(
        &mut pixels,
        target_width,
        target_height,
        settings,
        elapsed_seconds,
    );
    FrameData {
        width: target_width,
        height: target_height,
        pixels,
    }
}

fn compact_size(width: u32, height: u32, limited: bool) -> (u32, u32) {
    if !limited || width == 0 || height == 0 {
        return (width.max(1), height.max(1));
    }
    let scale = 1.0_f64
        .min((MAX_CACHED_PIXELS / (width as f64 * height as f64)).sqrt())
        .min(MAX_CACHED_DIMENSION / width.max(height) as f64);
    (
        (width as f64 * scale).round().max(1.0) as u32,
        (height as f64 * scale).round().max(1.0) as u32,
    )
}

fn apply_filter(
    pixels: &mut [u8],
    width: u32,
    height: u32,
    settings: &AppSettings,
    elapsed_seconds: f64,
) {
    let brightness = settings.brightness.clamp(0.10, 1.0);
    let brightness_lut = channel_lut(255, brightness);
    if settings.filter_style == FilterStyle::Original {
        for pixel in pixels.chunks_exact_mut(4) {
            pixel[0] = brightness_lut[pixel[0] as usize];
            pixel[1] = brightness_lut[pixel[1] as usize];
            pixel[2] = brightness_lut[pixel[2] as usize];
            pixel[3] = 255;
        }
        return;
    }

    let gray: Vec<u8> = pixels
        .chunks_exact(4)
        .map(|pixel| {
            (pixel[0] as f32 * 0.114 + pixel[1] as f32 * 0.587 + pixel[2] as f32 * 0.299)
                .clamp(0.0, 255.0) as u8
        })
        .collect();
    if settings.filter_style == FilterStyle::Grayscale {
        for (pixel, value) in pixels.chunks_exact_mut(4).zip(gray) {
            let value = brightness_lut[value as usize];
            pixel.copy_from_slice(&[value, value, value, 255]);
        }
        return;
    }

    let cycling = matches!(
        settings.filter_style,
        FilterStyle::MonoCycle | FilterStyle::EdgeCycle
    );
    let accent = if cycling {
        cycling_bgr(elapsed_seconds, settings.hue_cycle_seconds)
    } else {
        let color = settings.accent_color;
        [color as u8, (color >> 8) as u8, (color >> 16) as u8]
    };
    let intensity = if matches!(
        settings.filter_style,
        FilterStyle::Edge | FilterStyle::EdgeCycle
    ) {
        inner_edges(
            &gray,
            width as usize,
            height as usize,
            settings.edge_threshold,
            settings.edge_thickness,
        )
    } else {
        gray
    };
    let blue_lut = channel_lut(accent[0], brightness);
    let green_lut = channel_lut(accent[1], brightness);
    let red_lut = channel_lut(accent[2], brightness);
    for (pixel, value) in pixels.chunks_exact_mut(4).zip(intensity) {
        pixel[0] = blue_lut[value as usize];
        pixel[1] = green_lut[value as usize];
        pixel[2] = red_lut[value as usize];
        pixel[3] = 255;
    }
}

fn inner_edges(gray: &[u8], width: usize, height: usize, threshold: u8, thickness: u8) -> Vec<u8> {
    if width == 0 || height == 0 || gray.is_empty() {
        return vec![0_u8; gray.len()];
    }
    let mut horizontal_minimum = vec![0_u8; gray.len()];
    for y in 0..height {
        let row_start = y * width;
        for x in 0..width {
            let index = row_start + x;
            let mut value = gray[index];
            if x > 0 {
                value = value.min(gray[index - 1]);
            }
            if x + 1 < width {
                value = value.min(gray[index + 1]);
            }
            horizontal_minimum[index] = value;
        }
    }

    let mut edges = vec![0_u8; gray.len()];
    for y in 0..height {
        for x in 0..width {
            let index = y * width + x;
            let center = gray[index];
            let mut neighbor_minimum = horizontal_minimum[index];
            if y > 0 {
                neighbor_minimum = neighbor_minimum.min(horizontal_minimum[index - width]);
            }
            if y + 1 < height {
                neighbor_minimum = neighbor_minimum.min(horizontal_minimum[index + width]);
            }
            let difference = center.saturating_sub(neighbor_minimum);
            edges[index] = difference
                .saturating_sub(threshold.max(4))
                .saturating_mul(4);
        }
    }
    let mut expanded = vec![0_u8; gray.len()];
    for _ in 1..thickness.clamp(1, 4) {
        for y in 0..height {
            for x in 0..width {
                let index = y * width + x;
                let mut value = edges[index];
                if y > 0 && gray[index] >= gray[index - width] {
                    value = value.max(edges[index - width]);
                }
                if y + 1 < height && gray[index] >= gray[index + width] {
                    value = value.max(edges[index + width]);
                }
                if x > 0 && gray[index] >= gray[index - 1] {
                    value = value.max(edges[index - 1]);
                }
                if x + 1 < width && gray[index] >= gray[index + 1] {
                    value = value.max(edges[index + 1]);
                }
                expanded[index] = value;
            }
        }
        std::mem::swap(&mut edges, &mut expanded);
    }
    edges
}

fn channel_lut(channel: u8, brightness: f32) -> [u8; 256] {
    let mut result = [0_u8; 256];
    for (value, output) in result.iter_mut().enumerate() {
        *output = (channel as f32 * (value as f32 / 255.0 * brightness)) as u8;
    }
    result
}

fn cycling_bgr(elapsed_seconds: f64, period_seconds: u32) -> [u8; 3] {
    let hue = (elapsed_seconds / period_seconds.max(10) as f64).fract() as f32 * 6.0;
    let sector = hue.floor() as u8;
    let fraction = hue - hue.floor();
    let saturation = 0.82;
    let p = 1.0 - saturation;
    let q = 1.0 - fraction * saturation;
    let t = 1.0 - (1.0 - fraction) * saturation;
    let (red, green, blue) = match sector {
        0 => (1.0, t, p),
        1 => (q, 1.0, p),
        2 => (p, 1.0, t),
        3 => (p, q, 1.0),
        4 => (t, p, 1.0),
        _ => (1.0, p, q),
    };
    [
        (blue * 255.0) as u8,
        (green * 255.0) as u8,
        (red * 255.0) as u8,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(width: usize, height: usize, value: u8) -> Vec<u8> {
        [value, value, value, 255].repeat(width * height)
    }

    #[test]
    fn full_resolution_preserves_dimensions() {
        let mut settings = AppSettings::default();
        settings.limit_capture_resolution = false;
        let result = compact_and_filter(&frame(20, 10, 200), 20, 10, 80, &settings, 0.0);
        assert_eq!((result.width, result.height), (20, 10));
    }

    #[test]
    fn full_resolution_copy_skips_row_padding() {
        let mut settings = AppSettings::default();
        settings.limit_capture_resolution = false;
        settings.brightness = 1.0;
        let raw = [
            10, 20, 30, 255, 40, 50, 60, 255, 1, 2, 3, 4, 70, 80, 90, 255, 100, 110, 120, 255, 5,
            6, 7, 8,
        ];
        let result = compact_and_filter(&raw, 2, 2, 12, &settings, 0.0);
        assert_eq!(
            result.pixels,
            [
                10, 20, 30, 255, 40, 50, 60, 255, 70, 80, 90, 255, 100, 110, 120, 255,
            ]
        );
    }

    #[test]
    fn uniform_edge_frame_is_black() {
        let mut settings = AppSettings::default();
        settings.filter_style = FilterStyle::Edge;
        settings.brightness = 1.0;
        let result = compact_and_filter(&frame(8, 8, 200), 8, 8, 32, &settings, 0.0);
        assert!(
            result
                .pixels
                .chunks_exact(4)
                .all(|pixel| pixel[..3] == [0, 0, 0])
        );
    }

    #[test]
    fn inner_edge_never_lights_dark_background() {
        let width = 9;
        let height = 9;
        let mut input = frame(width, height, 0);
        for y in 2..7 {
            for x in 2..7 {
                let index = (y * width + x) * 4;
                input[index..index + 3].copy_from_slice(&[180, 180, 180]);
            }
        }
        let mut settings = AppSettings::default();
        settings.filter_style = FilterStyle::Edge;
        settings.brightness = 1.0;
        let result = compact_and_filter(
            &input,
            width as u32,
            height as u32,
            (width * 4) as u32,
            &settings,
            0.0,
        );
        for (source, output) in input.chunks_exact(4).zip(result.pixels.chunks_exact(4)) {
            if source[0] == 0 {
                assert_eq!(&output[..3], &[0, 0, 0]);
            }
        }
    }

    #[test]
    fn separable_inner_edge_matches_reference_algorithm() {
        let width = 7;
        let height = 5;
        let gray: Vec<u8> = (0..width * height)
            .map(|index| ((index * 47 + index / 3 * 19) % 256) as u8)
            .collect();
        for thickness in 1..=4 {
            assert_eq!(
                inner_edges(&gray, width, height, 21, thickness),
                reference_inner_edges(&gray, width, height, 21, thickness)
            );
        }
    }

    fn reference_inner_edges(
        gray: &[u8],
        width: usize,
        height: usize,
        threshold: u8,
        thickness: u8,
    ) -> Vec<u8> {
        let mut edges = vec![0_u8; gray.len()];
        for y in 0..height {
            for x in 0..width {
                let index = y * width + x;
                let center = gray[index];
                let mut neighbor_minimum = center;
                for neighbor_y in y.saturating_sub(1)..=(y + 1).min(height - 1) {
                    for neighbor_x in x.saturating_sub(1)..=(x + 1).min(width - 1) {
                        neighbor_minimum =
                            neighbor_minimum.min(gray[neighbor_y * width + neighbor_x]);
                    }
                }
                edges[index] = center
                    .saturating_sub(neighbor_minimum)
                    .saturating_sub(threshold.max(4))
                    .saturating_mul(4);
            }
        }
        for _ in 1..thickness.clamp(1, 4) {
            let previous = edges.clone();
            for y in 0..height {
                for x in 0..width {
                    let index = y * width + x;
                    let mut value = previous[index];
                    if y > 0 && gray[index] >= gray[index - width] {
                        value = value.max(previous[index - width]);
                    }
                    if y + 1 < height && gray[index] >= gray[index + width] {
                        value = value.max(previous[index + width]);
                    }
                    if x > 0 && gray[index] >= gray[index - 1] {
                        value = value.max(previous[index - 1]);
                    }
                    if x + 1 < width && gray[index] >= gray[index + 1] {
                        value = value.max(previous[index + 1]);
                    }
                    edges[index] = value;
                }
            }
        }
        edges
    }
}
