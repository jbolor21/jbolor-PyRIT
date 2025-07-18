# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import json
import logging
import uuid
from typing import Optional

from pyrit.exceptions import (
    InvalidJsonException,
    pyrit_json_retry,
    remove_markdown_json,
)
from pyrit.models import (
    PromptDataType,
    PromptRequestPiece,
    PromptRequestResponse,
    SeedPrompt,
)
from pyrit.prompt_converter import ConverterResult, PromptConverter
from pyrit.prompt_target import PromptChatTarget

logger = logging.getLogger(__name__)


class FuzzerConverter(PromptConverter):
    """
    Base class for GPTFUZZER converters.

    Adapted from GPTFUZZER: Red Teaming Large Language Models with Auto-Generated Jailbreak Prompts.
    Paper: https://arxiv.org/pdf/2309.10253 by Jiahao Yu, Xingwei Lin, Zheng Yu, Xinyu Xing.
    GitHub: https://github.com/sherdencooper/GPTFuzz/tree/master
    """

    def __init__(self, *, converter_target: PromptChatTarget, prompt_template: Optional[SeedPrompt] = None):
        """
        Initializes the converter with the specified chat target and prompt template.

        Args:
            converter_target (PromptChatTarget): Chat target used to perform fuzzing on user prompt.
            prompt_template (SeedPrompt, Optional): Template to be used instead of the default system prompt with
                instructions for the chat target.
        """
        self.converter_target = converter_target
        self.system_prompt = prompt_template.value
        self.template_label = "TEMPLATE"

    def update(self, **kwargs) -> None:
        """Updates the converter with new parameters."""
        pass

    async def convert_async(self, *, prompt: str, input_type: PromptDataType = "text") -> ConverterResult:
        """
        Converts the given prompt into the target format supported by the converter.

        Args:
            prompt (str): The prompt to be converted.
            input_type (PromptDataType): The type of input data.

        Returns:
            ConverterResult: The result containing the modified prompt.

        Raises:
            ValueError: If the input type is not supported.
        """
        if not self.input_supported(input_type):
            raise ValueError("Input type not supported")

        conversation_id = str(uuid.uuid4())

        self.converter_target.set_system_prompt(
            system_prompt=self.system_prompt,
            conversation_id=conversation_id,
            orchestrator_identifier=None,
        )

        formatted_prompt = f"===={self.template_label} BEGINS====\n{prompt}\n===={self.template_label} ENDS===="
        prompt_metadata: dict[str, str | int] = {"response_format": "json"}
        request = PromptRequestResponse(
            [
                PromptRequestPiece(
                    role="user",
                    original_value=formatted_prompt,
                    converted_value=formatted_prompt,
                    conversation_id=conversation_id,
                    sequence=1,
                    prompt_target_identifier=self.converter_target.get_identifier(),
                    original_value_data_type=input_type,
                    converted_value_data_type=input_type,
                    converter_identifiers=[self.get_identifier()],
                    prompt_metadata=prompt_metadata,
                )
            ]
        )

        response = await self.send_prompt_async(request)

        return ConverterResult(output_text=response, output_type="text")

    @pyrit_json_retry
    async def send_prompt_async(self, request):
        """Sends the prompt request to the converter target and processes the response."""
        response = await self.converter_target.send_prompt_async(prompt_request=request)

        response_msg = response.get_value()
        response_msg = remove_markdown_json(response_msg)

        try:
            parsed_response = json.loads(response_msg)
            if "output" not in parsed_response:
                raise InvalidJsonException(message=f"Invalid JSON encountered; missing 'output' key: {response_msg}")
            return parsed_response["output"]

        except json.JSONDecodeError:
            raise InvalidJsonException(message=f"Invalid JSON encountered: {response_msg}")

    def input_supported(self, input_type: PromptDataType) -> bool:
        return input_type == "text"

    def output_supported(self, output_type: PromptDataType) -> bool:
        return output_type == "text"
