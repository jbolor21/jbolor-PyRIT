# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import json
from typing import Callable, Union
import requests
from pyrit.prompt_target import PromptTarget
from pyrit.memory import MemoryInterface
from pyrit.models import construct_response_from_request, PromptRequestPiece, PromptRequestResponse
import urllib.parse
import re

logger = logging.getLogger(__name__)


class HTTPTarget(PromptTarget):
    """
    HTTP_Target is for endpoints that do not have an API and instead require HTTP request(s) to send a prompt
    Parameters:
        http_request (str): the header parameters as a request (ie from Burp)
        prompt_regex_string (str): the placeholder for the prompt
            (defuault is {PROMPT}) which will be replaced by the actual prompt.
            make sure to modify the http request to have this included, otherwise it will not be properly replaced!
        response_parse_key (str): this is the path pattern to follow for parsing the output response
            (ie for AOAI this would be choices[0].message.content)
        callback_function (function): function to parse HTTP response.
            These are the customizable functions which determine how to parse the output
        memory : memory interface
    """

    def __init__(
        self,
        http_request: str = None,
        prompt_regex_string: str = "{PROMPT}",
        response_parse_key: str = "",
        callback_function: Callable = None,
        memory: Union[MemoryInterface, None] = None,
    ) -> None:

        super().__init__(memory=memory)
        self.http_request = http_request
        self.callback_function = callback_function
        self.prompt_regex_string = prompt_regex_string
        self.response_parse_key = response_parse_key
        #kwargs

    async def send_prompt_async(self, *, prompt_request: PromptRequestResponse) -> PromptRequestResponse:
        """
        Sends prompt to HTTP endpoint and returns the response
        """

        self._validate_request(prompt_request=prompt_request)
        request = prompt_request.request_pieces[0]

        header_dict, http_body, url, http_method = self.parse_raw_http_request()
        re_pattern = re.compile(self.prompt_regex_string)

        # Make the actual HTTP request:

        # Checks if the body is a json object - this matters when we substitute in the prompt for the placeholder
        try:
            json.loads(http_body)
            http_body_json = True
        except (ValueError, json.JSONDecodeError):
            http_body_json = False

        # Add Prompt into URL (if the URL takes it)
        if re.search(self.prompt_regex_string, url):
            prompt_url_safe = urllib.parse.quote(
                request.original_value
            )  # by default doing URL encoding for prompts that go in URL
            formatted_url = re_pattern.sub(prompt_url_safe, url)
            url = formatted_url

        # Add Prompt into request body (if the body takes it)
        if re.search(self.prompt_regex_string, http_body):
            if http_body_json:  # clean prompt of whitespace control characters to ensure still valid json
                cleaned_prompt = re.sub(r"\s", " ", request.original_value)
                formatted_http_body = re_pattern.sub(cleaned_prompt, http_body)
            else:  # doesn't clean prompt, enters it all in
                formatted_http_body = re_pattern.sub(request.original_value, http_body)

            http_body = formatted_http_body

            response = requests.request(
                url=url,
                headers=header_dict,
                data=http_body,
                method=http_method,
                allow_redirects=True,  # using Requests so we can leave this flag on, rather than httpx
            )

        if self.callback_function:
            parsed_response = self.callback_function(response=response, key=self.response_parse_key) #kwargs instead

            response_entry = construct_response_from_request(
                request=request, response_text_pieces=[str(parsed_response)]
            )

        else:
            response_entry = construct_response_from_request(
                request=request, response_text_pieces=[str(response.content)]
            )
        return response_entry

    def parse_raw_http_request(self):
        """
        Parses the HTTP request string into a dictionary of headers
        Returns:
            headers_dict (dict): dictionary of all http header values
            body (str): string with body data
            url (str): string with URL
            http_method (str): method (ie GET vs POST)
        """

        headers_dict = {}
        if not self.http_request:
            return {}, "", "", ""

        body = ""

        # Split the request into headers and body by finding the double newlines (\n\n)
        request_parts = self.http_request.strip().split("\n\n", 1)

        # Parse out the header components
        header_lines = request_parts[0].strip().split("\n")
        http_req_info_line = header_lines[0].split(" ")  # get 1st line like POST /url_ending HTTP_VSN
        header_lines = header_lines[1:]  # rest of the raw request is the headers info

        # Loop through each line and split into key-value pairs
        for line in header_lines:
            key, value = line.split(":", 1)
            headers_dict[key.strip()] = value.strip()

        if len(request_parts) > 1:
            # Parse as JSON object if it can be parsed that way
            try:
                body = json.loads(request_parts[1], strict=False)  # Check if valid json
                body = json.dumps(body)
            except json.JSONDecodeError:
                body = request_parts[1]
            if "Content-Length" in headers_dict:
                headers_dict["Content-Length"] = str(len(body))

        # Capture info from 1st line of raw request
        http_method = http_req_info_line[0]

        http_url_beg = ""
        if len(http_req_info_line) > 2:
            http_version = http_req_info_line[2]
            # TODO: qn use_tls_flag variable instead?
            if "HTTP/2" in http_version:
                http_url_beg = "https://"
            elif "HTTP/1.1" in http_version:
                http_url_beg = "http://"
            else:
                raise ValueError(f"Unsupported protocol: {http_version}")

        url = ""
        if http_url_beg and "http" not in http_req_info_line[1]:
            url = http_url_beg
        if "Host" in headers_dict.keys():
            url += headers_dict["Host"]
        url += http_req_info_line[1]

        return headers_dict, body, url, http_method

    def _validate_request(self, *, prompt_request: PromptRequestResponse) -> None:
        request_pieces: list[PromptRequestPiece] = prompt_request.request_pieces

        if len(request_pieces) != 1:
            raise ValueError("This target only supports a single prompt request piece.")


# doc NEEDING this response
def parse_json_http_response(response, key: str): # kwargs here
    json_response = json.loads(response.content)
    data_key = fetch_key(data=json_response, key=key)
    return data_key


def parse_html_response(response, key: str):
    print(response.content)
    try:
        #TODO: remove this later, for now saving output in case
        with open("BIC_OUTPUT_2.html", 'w', encoding='utf-8') as file:
            file.write(str(response.content))
        print("Content saved successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    re_pattern = r'\/images\/create\/async\/results\/[^\s"]+' #TODO make this a variable
    match = re.search(re_pattern, str(response.content))
    if match:
        print(match.group())
        return "https://bing.com" + match.group()
    else:
        print("ERROR did not find match")
        return str(response.content)


def fetch_key(data: dict, key: str) -> str:
    """
    Credit to @Mayuraggarwal1992
    Fetches the answer from the HTTP JSON response based on the path.

    Args:
        data (dict): HTTP response data.
        key (str): The key path to fetch the value.

    Returns:
        str: The fetched value.
    """
    pattern = re.compile(r"([a-zA-Z_]+)|\[(\d+)\]")
    keys = pattern.findall(key)
    for key_part, index_part in keys:
        if key_part:
            data = data.get(key_part, None)
        elif index_part and isinstance(data, list):
            data = data[int(index_part)] if len(data) > int(index_part) else None
        if data is None:
            return ""
    return data
