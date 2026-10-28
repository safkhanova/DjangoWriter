"""Shared helpers: Azerbaijani slugs, upload validation, image optimisation, HTML sanitising."""

import os
import re
from io import BytesIO

import nh3
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from PIL import Image, ImageOps

AZ_TRANSLIT = str.maketrans(
    {
        "ə": "e", "Ə": "e",
        "ı": "i", "I": "i", "İ": "i",
        "ş": "sh", "Ş": "sh",
        "ç": "ch", "Ç": "ch",
        "ğ": "g", "Ğ": "g",
        "ö": "o", "Ö": "o",
        "ü": "u", "Ü": "u",
    }
)


def az_slugify(value: str, max_length: int = 80) -> str:
    """Slug with Azerbaijani transliteration: "Şeirin adı" -> "sheirin-adi"."""
    slug = slugify(str(value).translate(AZ_TRANSLIT))
    return slug[:max_length].strip("-")


def unique_slug(instance, value: str, slug_field: str = "slug", max_length: int = 80, **scope) -> str:
    """Return a slug that is unique for `instance`'s model within the given `scope` filter."""
    base = az_slugify(value, max_length) or "yazi"
    model = type(instance)
    candidate, n = base, 2
    while model.objects.filter(**{slug_field: candidate}, **scope).exclude(pk=instance.pk).exists():
        suffix = f"-{n}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        n += 1
    return candidate


# --- Upload validators ------------------------------------------------------

def validate_image_size(file):
    limit = settings.MAX_IMAGE_UPLOAD_MB
    if file and file.size > limit * 1024 * 1024:
        raise ValidationError(f"Şəkil çox böyükdür. Maksimum ölçü {limit} MB-dır.")


def validate_document_size(file):
    limit = settings.MAX_DOCUMENT_UPLOAD_MB
    if file and file.size > limit * 1024 * 1024:
        raise ValidationError(f"Fayl çox böyükdür. Maksimum ölçü {limit} MB-dır.")


SVG_FORBIDDEN = re.compile(rb"<script|javascript:|\bon[a-z]+\s*=|<foreignobject|<iframe|<embed|<object", re.I)


def validate_safe_svg(file):
    """Reject SVGs carrying scripts or event handlers (an SVG is served as a document)."""
    if file and file.name.lower().endswith(".svg"):
        file.seek(0)
        content = file.read()
        file.seek(0)
        if SVG_FORBIDDEN.search(content):
            raise ValidationError("Bu SVG faylında icazə verilməyən kod var. PNG və ya təmiz SVG yükləyin.")


logo_validators = [
    FileExtensionValidator(["png", "jpg", "jpeg", "webp", "svg"]), validate_image_size, validate_safe_svg,
]
favicon_validators = [FileExtensionValidator(["ico", "png", "svg"]), validate_image_size, validate_safe_svg]


# --- Image optimisation -----------------------------------------------------

MAX_IMAGE_SIDE = 2400


def optimize_image_field(field_file, max_side: int = MAX_IMAGE_SIDE, quality: int = 85) -> bool:
    """
    Re-encode a freshly uploaded image as WebP, fix EXIF rotation and cap its size.

    Only touches files that have not been committed to storage yet (new uploads),
    so editing an article without changing the image does nothing.
    Returns True when the file was replaced.
    """
    if not field_file or getattr(field_file, "_committed", True):
        return False
    name = os.path.basename(field_file.name)
    if name.lower().endswith((".svg", ".gif")):
        return False
    try:
        field_file.open()
        img = Image.open(field_file)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=6)
    except Exception:  # not a decodable image: keep the original upload
        return False
    stem = os.path.splitext(name)[0]
    field_file.save(f"{stem}.webp", ContentFile(buffer.getvalue()), save=False)
    return True


class OptimizedImagesMixin:
    """Model mixin: lists `optimized_image_fields` that are converted on save."""

    optimized_image_fields: tuple[str, ...] = ()

    def save(self, *args, **kwargs):
        for field_name in self.optimized_image_fields:
            optimize_image_field(getattr(self, field_name))
        super().save(*args, **kwargs)


# --- Rich text --------------------------------------------------------------

ALLOWED_TAGS = {
    "p", "div", "br", "strong", "b", "em", "i", "u", "del", "s",
    "a", "ul", "ol", "li", "h1", "h2", "h3", "blockquote",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}


def sanitize_html(value: str) -> str:
    """Strip anything that is not basic formatting (scripts, styles, iframes...)."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto", "tel"},
        link_rel="noopener noreferrer",
    )


def is_preview_user(user) -> bool:
    """Logged-in staff see drafts, hidden sections and hidden blocks (preview mode)."""
    return bool(user and user.is_authenticated and user.is_staff)
