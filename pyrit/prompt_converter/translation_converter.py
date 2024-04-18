import json
import logging
import uuid
import pathlib

from pyrit.models import PromptDataType
from pyrit.models import PromptRequestPiece, PromptRequestResponse
from pyrit.prompt_converter import PromptConverter
from pyrit.models import PromptTemplate
from pyrit.common.path import DATASETS_PATH
from pyrit.prompt_target import PromptChatTarget
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


class TranslationConverter(PromptConverter):
    def __init__(self, *, converter_target: PromptChatTarget, language: str, prompt_template: PromptTemplate = None):
        """
        Initializes a TranslationConverter object.

        Args:
            converter_target (PromptChatTarget): The target chat support for the conversion which will translate
            language (str): The language for the conversion. E.g. Spanish, French, leetspeak, etc.
            prompt_template (PromptTemplate, optional): The prompt template for the conversion.

        Raises:
            ValueError: If the language is not provided.
        """
        self.converter_target = converter_target

        # set to default strategy if not provided
        prompt_template = (
            prompt_template
            if prompt_template
            else PromptTemplate.from_yaml_file(
                pathlib.Path(DATASETS_PATH) / "prompt_converters" / "translation_converter.yaml"
            )
        )

        if not language:
            raise ValueError("Language must be provided for translation conversion")

        self.language = language

        self.system_prompt = prompt_template.apply_custom_metaprompt_parameters(languages=language)
        self._labels = {"converter": "TranslationConverter"}

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    def convert(self, *, prompt: str, input_type: PromptDataType = "text") -> str:
        """
        Generates variations of the input prompts using the converter target.
        Parameters:
            prompts: list of prompts to convert
        Return:
            target_responses: list of prompt variations generated by the converter target
        """

        conversation_id = str(uuid.uuid4())

        self.converter_target.set_system_prompt(
            system_prompt=self.system_prompt,
            conversation_id=conversation_id,
            orchestrator_identifier=None,
            labels=self._labels,
        )

        if not self.is_supported(input_type):
            raise ValueError("Input type not supported")

        request = PromptRequestResponse(
            [
                PromptRequestPiece(
                    role="user",
                    original_prompt_text=prompt,
                    converted_prompt_text=prompt,
                    conversation_id=conversation_id,
                    sequence=1,
                    labels=self._labels,
                    prompt_target_identifier=self.converter_target.get_identifier(),
                    original_prompt_data_type=input_type,
                    converted_prompt_data_type=input_type,
                )
            ]
        )

        response_msg = self.converter_target.send_prompt(prompt_request=request).request_pieces[0].converted_prompt_text

        try:
            llm_response: dict[str, str] = json.loads(response_msg)["output"]
            return llm_response[self.language]

        except json.JSONDecodeError as e:
            logger.warn(f"Error in LLM response {response_msg}: {e}")
            raise RuntimeError(f"Error in LLM respons {response_msg}")

    def is_supported(self, input_type: PromptDataType) -> bool:
        return input_type == "text"
