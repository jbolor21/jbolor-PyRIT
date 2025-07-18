# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from azure.core.exceptions import ClientAuthenticationError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import ContainerClient as AsyncContainerClient

from pyrit.auth import AzureStorageAuth
from pyrit.common import default_values
from pyrit.models import PromptRequestResponse, construct_response_from_request
from pyrit.prompt_target import PromptTarget, limit_requests_per_minute

logger = logging.getLogger(__name__)


class SupportedContentType(Enum):
    """
    All supported content types for uploading blobs to provided storage account container.
    See all options here: https://www.iana.org/assignments/media-types/media-types.xhtml
    """

    PLAIN_TEXT = "text/plain"


class AzureBlobStorageTarget(PromptTarget):
    """
    The AzureBlobStorageTarget takes prompts, saves the prompts to a file, and stores them as a blob in a provided
    storage account container.

    Args:
        container_url (str): URL to the Azure Blob Storage Container.
        sas_token (optional[str]): Optional Blob SAS token needed to authenticate blob operations. If not provided, a
            delegation SAS token will be created using Entra ID authentication.
        blob_content_type (SupportedContentType): Expected Content Type of the blob, chosen from the
            SupportedContentType enum. Set to PLAIN_TEXT by default.
        max_requests_per_minute (int, Optional): Number of requests the target can handle per
            minute before hitting a rate limit. The number of requests sent to the target
            will be capped at the value provided.
    """

    AZURE_STORAGE_CONTAINER_ENVIRONMENT_VARIABLE: str = "AZURE_STORAGE_ACCOUNT_CONTAINER_URL"
    SAS_TOKEN_ENVIRONMENT_VARIABLE: str = "AZURE_STORAGE_ACCOUNT_SAS_TOKEN"

    def __init__(
        self,
        *,
        container_url: Optional[str] = None,
        sas_token: Optional[str] = None,
        blob_content_type: SupportedContentType = SupportedContentType.PLAIN_TEXT,
        max_requests_per_minute: Optional[int] = None,
    ) -> None:

        self._blob_content_type: str = blob_content_type.value

        self._container_url: str = default_values.get_required_value(
            env_var_name=self.AZURE_STORAGE_CONTAINER_ENVIRONMENT_VARIABLE, passed_value=container_url
        )

        self._sas_token = sas_token
        self._client_async: AsyncContainerClient = None

        super().__init__(max_requests_per_minute=max_requests_per_minute)

    async def _create_container_client_async(self) -> None:
        """Creates an asynchronous ContainerClient for Azure Storage. If a SAS token is provided via the
        AZURE_STORAGE_ACCOUNT_SAS_TOKEN environment variable or the init sas_token parameter, it will be used
        for authentication. Otherwise, a delegation SAS token will be created using Entra ID authentication."""
        container_url, _ = self._parse_url()
        try:
            sas_token: str = default_values.get_required_value(
                env_var_name=self.SAS_TOKEN_ENVIRONMENT_VARIABLE, passed_value=self._sas_token
            )
            logger.info("Using SAS token from environment variable or passed parameter.")
        except ValueError:
            logger.info("SAS token not provided. Creating a delegation SAS token using Entra ID authentication.")
            sas_token = await AzureStorageAuth.get_sas_token(container_url)
        self._client_async = AsyncContainerClient.from_container_url(
            container_url=container_url,
            credential=sas_token,
        )

    async def _upload_blob_async(self, file_name: str, data: bytes, content_type: str) -> None:
        """
        (Async) Handles uploading blob to given storage container.

        Args:
            file_name (str): File name to assign to uploaded blob.
            data (bytes): Byte representation of content to upload to container.
            content_type (str): Content type to upload.
        """

        content_settings = ContentSettings(content_type=f"{content_type}")
        logger.info(msg="\nUploading to Azure Storage as blob:\n\t" + file_name)

        if not self._client_async:
            await self._create_container_client_async()
        # Parse the Azure Storage Blob URL to extract components
        _, blob_prefix = self._parse_url()
        blob_path = f"{blob_prefix}/{file_name}"
        try:
            blob_client = self._client_async.get_blob_client(blob=blob_path)
            await blob_client.upload_blob(data=data, content_settings=content_settings)
        except Exception as exc:
            if isinstance(exc, ClientAuthenticationError):
                logger.exception(
                    msg="Authentication failed. Please check that the container existence in the "
                    + "Azure Storage Account and ensure the validity of the provided SAS token. If you "
                    + "haven't set the SAS token as an environment variable use `az login` to "
                    + "enable delegation-based SAS authentication to connect to the storage account"
                )
                raise
            else:
                logger.exception(msg=f"An unexpected error occurred: {exc}")
                raise

    def _parse_url(self):
        """Parses the Azure Storage Blob URL to extract components."""
        parsed_url = urlparse(self._container_url)
        path_parts = parsed_url.path.split("/")
        container_name = path_parts[1]
        blob_prefix = "/".join(path_parts[2:])
        container_url = f"https://{parsed_url.netloc}/{container_name}"
        return container_url, blob_prefix

    @limit_requests_per_minute
    async def send_prompt_async(self, *, prompt_request: PromptRequestResponse) -> PromptRequestResponse:
        """
        (Async) Sends prompt to target, which creates a file and uploads it as a blob
        to the provided storage container.

        Args:
            normalized_prompt (str): A normalized prompt to be sent to the prompt target.
            conversation_id (str): The ID of the conversation.
            normalizer_id (str): ID provided by the prompt normalizer.

        Returns:
            blob_url (str): The Blob URL of the created blob within the provided storage container.
        """
        self._validate_request(prompt_request=prompt_request)
        request = prompt_request.request_pieces[0]

        file_name = f"{request.conversation_id}.txt"
        data = str.encode(request.converted_value)
        blob_url = self._container_url + "/" + file_name

        await self._upload_blob_async(file_name=file_name, data=data, content_type=self._blob_content_type)

        response = construct_response_from_request(
            request=request, response_text_pieces=[blob_url], response_type="url"
        )

        return response

    def _validate_request(self, *, prompt_request: PromptRequestResponse) -> None:
        n_pieces = len(prompt_request.request_pieces)
        if n_pieces != 1:
            raise ValueError(f"This target only supports a single prompt request piece. Received {n_pieces} pieces")

        piece_type = prompt_request.request_pieces[0].converted_value_data_type
        if piece_type not in ["text", "url"]:
            raise ValueError(f"This target only supports text and url prompt input. Received: {piece_type}.")

        request = prompt_request.request_pieces[0]
        messages = self._memory.get_chat_messages_with_conversation_id(conversation_id=request.conversation_id)

        if len(messages) > 0:
            raise ValueError("This target only supports a single turn conversation.")
