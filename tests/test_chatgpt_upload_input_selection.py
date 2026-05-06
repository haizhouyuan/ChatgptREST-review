from chatgpt_web_mcp._tools_impl import _chatgpt_should_skip_file_input


def test_chatgpt_generic_upload_files_input_is_usable_for_non_images() -> None:
    assert _chatgpt_should_skip_file_input(
        input_id="upload-files",
        accept="",
        is_image=False,
    ) is False


def test_chatgpt_photo_only_inputs_are_skipped_for_non_images() -> None:
    assert _chatgpt_should_skip_file_input(
        input_id="upload-photos",
        accept="image/*",
        is_image=False,
    ) is True
    assert _chatgpt_should_skip_file_input(
        input_id="upload-camera",
        accept="image/*",
        is_image=False,
    ) is True


def test_chatgpt_image_accept_input_is_rejected_for_non_image_files() -> None:
    assert _chatgpt_should_skip_file_input(
        input_id="generic-input",
        accept="image/*",
        is_image=False,
    ) is True

