# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import pathlib

from augly.image.transforms import OverlayText
from augly.utils import base_paths

from pyrit.models.data_type_serializer import data_serializer_factory
from pyrit.models.prompt_request_piece import PromptDataType
from pyrit.prompt_converter import PromptConverter, ConverterResult

logger = logging.getLogger(__name__)


class AddTextImageConverter(PromptConverter):
    """
    Adds a string to an image

    Args:
        font (optional, str): path of font to use - will set to source sans pro as default
        color (optional, tuple): color to print text in, using RGB values, black is the default if not provided
        font_size (optional, float): size of font to use
        x_pos (optional, float): x coordinate to place text in (0 is left most)
        y_pos (optional, float): y coordinate to place text in (0 is upper most)

    """

    def __init__(
        self,
        font: str = str(pathlib.Path(base_paths.FONTS_DIR) / "SourceSansPro-Black.ttf"),
        color: tuple[int, int, int] = (255, 255, 255),
        font_size: float = 0.05,
        x_pos: int = 0,
        y_pos: int = 0,
    ):
        self._font = font
        self._font_size = font_size
        self._color = color
        self._x = x_pos
        self._y = y_pos

    def convert(self, *, prompt: str, input_type: PromptDataType = "image_path", **kwargs) -> ConverterResult:
        """
        Converter that adds text to an image

        Args:
            prompt (str): The prompt to be added to the image.
            input_type (PromptDataType): type of data
            kwargs (dict): holds input "text_to_add" as a list with each line of text as a list entry
        Returns:
            ConverterResult: The filename of the converted image as a ConverterResult Object
        """
        if not self.input_supported(input_type):
            raise ValueError("Input type not supported")

        data = data_serializer_factory(value=prompt, data_type="image_path")

        # Open the image
        original_img = data.read_data_image()
        text_ascii_int_list = []

        if "text_to_add" in kwargs:
            # Splits prompt into list[int] representation needed for augly
            text_to_add = kwargs["text_to_add"]

            for line in text_to_add:  # Each line of text to add is stored as a list
                """
                Converts each character to an integer representation
                this is the ascii encoding of the character subtracting 32,
                the numerical variance between uppercase (A -> 65) and lowercase characters (a -> 97)
                """
                print(line)
                text_to_int_line = list(ord(c) - 32 for c in line)
                text_ascii_int_list.append(text_to_int_line)

        else:
            raise ValueError("text_to_add is required")

        try:
            overlay_text = OverlayText(
                text=text_ascii_int_list,
                font_file=self._font,
                color=self._color,
                font_size=self._font_size,
                x_pos=self._x,
                y_pos=self._y,
            )
            new_img = overlay_text.apply_transform(image=original_img)
            data.save_image(new_img)

        except Exception as e:
            logger.error(f"Encountered an error while adding text '{text_to_add}' to the input image: {e}")
            raise

        return ConverterResult(output_text=data.value, output_type="image_path")

    def input_supported(self, input_type: PromptDataType) -> bool:
        return input_type == "image_path"
