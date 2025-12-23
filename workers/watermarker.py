from PIL import Image
import io

def add_watermark(base_img_data, watermark_path, opacity, output_format):
    # (保持与之前代码中的 process_tiled_watermark 函数完全相同)
    base_img = Image.open(base_img_data).convert("RGBA")
    watermark_img = Image.open(watermark_path).convert("RGBA")

    alpha = watermark_img.getchannel('A')
    alpha = alpha.point(lambda p: p * opacity)
    watermark_img.putalpha(alpha)

    base_w, base_h = base_img.size
    wm_w, wm_h = watermark_img.size

    tiled_watermark = Image.new('RGBA', (base_w, base_h), (0, 0, 0, 0))
    for x in range(0, base_w, wm_w):
        for y in range(0, base_h, wm_h):
            tiled_watermark.paste(watermark_img, (x, y), mask=watermark_img)

    final_img = Image.alpha_composite(base_img, tiled_watermark)

    output_buffer = io.BytesIO()
    
    if output_format == 'JPEG':
        final_img.convert('RGB').save(output_buffer, format="JPEG", quality=95)
    else:
        final_img.save(output_buffer, format="PNG")
        
    output_buffer.seek(0)
    return output_buffer
