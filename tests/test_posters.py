"""Image uploads: the real file type is checked, images are shrunk, and files stay inside the posters folder."""

import io

import pytest
from conftest import PNG, form, image_bytes
from PIL import Image

from app import posters
from app.database import DATA_DIR
from app.posters import POSTER_DIR

JPG = image_bytes("JPEG")
WEBP = image_bytes("WEBP")


def opened(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


@pytest.mark.parametrize("data", [PNG, JPG, WEBP])
def test_accepted_types_are_stored_as_webp(data):
    stored, extension = posters.read_poster(io.BytesIO(data))
    assert extension == ".webp"
    assert opened(stored).format == "WEBP"


@pytest.mark.parametrize(
    "data",
    [b"", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"just text"],
)
def test_other_files_are_rejected(data):
    with pytest.raises(posters.PosterError):
        posters.read_poster(io.BytesIO(data))


def test_right_signature_but_broken_file_is_rejected():
    with pytest.raises(posters.PosterError, match="couldn't be read"):
        posters.read_poster(io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64))


def test_size_limit():
    with pytest.raises(posters.PosterError, match="too large"):
        posters.read_poster(io.BytesIO(PNG + b"\x00" * posters.MAX_POSTER_BYTES))


def test_big_images_are_shrunk_keeping_their_shape():
    big = image_bytes("JPEG", size=(2000, 3000))
    stored, _ = posters.read_poster(io.BytesIO(big))
    assert opened(stored).size == (533, 800)
    assert len(stored) < len(big)


def test_transparency_is_kept():
    output = io.BytesIO()
    Image.new("RGBA", (40, 25), (255, 255, 255, 0)).save(output, "PNG")  # fully see-through
    stored, _ = posters.read_poster(io.BytesIO(output.getvalue()))
    assert opened(stored).mode == "RGBA"


def test_photo_metadata_is_removed():
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # camera maker; GPS data would be stripped the same way
    output = io.BytesIO()
    Image.new("RGB", (40, 25)).save(output, "JPEG", exif=exif)
    stored, _ = posters.read_poster(io.BytesIO(output.getvalue()))
    assert b"SecretCam" not in stored


def test_decompression_bomb_is_refused():
    # A tiny file that would unpack into 64 million pixels.
    with pytest.raises(posters.PosterError, match="too many pixels"):
        posters.read_poster(io.BytesIO(image_bytes("PNG", size=(8000, 8000), mode="1")))


def test_saved_under_a_random_name():
    first, second = posters.save_poster(PNG, ".png"), posters.save_poster(PNG, ".png")
    assert first != second and first.endswith(".png")
    assert (POSTER_DIR / first).read_bytes() == PNG


def test_delete_cannot_leave_the_posters_folder():
    outside = DATA_DIR / "keep-me.txt"
    outside.write_text("important")
    posters.delete_poster("../keep-me.txt")
    assert outside.exists()
    outside.unlink()


# --- Through the web forms ---


def upload(client, url, data, content=PNG, name="cover.png"):
    return client.post(url, data=data, files={"poster": (name, content, "application/octet-stream")})


def test_upload_is_saved_and_served(client, db):
    assert upload(client, "/titles", form()).status_code == 303
    files = list(POSTER_DIR.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".webp"
    assert client.get(f"/posters/{files[0].name}").status_code == 200


def test_fake_image_is_rejected_and_nothing_is_saved(client):
    response = upload(client, "/titles", form(), content=b"not an image")
    assert response.status_code == 422
    assert "Please upload a JPG, PNG or WebP image." in response.text
    assert not any(POSTER_DIR.iterdir())


def test_replacing_and_removing_cleans_up_old_files(client, make_title):
    item = make_title()
    upload(client, f"/titles/{item.id}/edit", form())
    (first,) = POSTER_DIR.iterdir()

    upload(client, f"/titles/{item.id}/edit", form(), content=JPG, name="new.jpg")
    (second,) = POSTER_DIR.iterdir()
    assert second.name != first.name

    client.post(f"/titles/{item.id}/edit", data=form(remove_poster="1"))
    assert not any(POSTER_DIR.iterdir())


def test_deleting_a_title_deletes_its_image(client, make_title):
    item = make_title()
    upload(client, f"/titles/{item.id}/edit", form())
    client.post(f"/titles/{item.id}/delete")
    assert not any(POSTER_DIR.iterdir())
