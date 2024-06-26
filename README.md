# FeverGPT

FeverGPT is released under the [0BSD License](COPYING).
- The author is not responsible for any damage, loss, or issues arising from the use or misuse of this 0BSD licensed software.  
The summary below is from [tl;drLegal](https://www.tldrlegal.com/license/bsd-0-clause-license).
- The BSD 0-clause license goes further than the 2-clause license to allow you unlimited freedom with the software without the requirements to include the copyright notice, license text, or disclaimer in either source or binary forms.

## Plugins

This tool uses a lightly modified version of [andylokandy's GPT4 CLI tool](https://github.com/andylokandy/gpt-4-search) as a temporary backend, which is released under an [MIT license](https://github.com/rakinishraq/gpt-4-search/blob/main/LICENSE).

**To download and use my fork,**  go to the [repository](https://github.com/rakinishraq/gpt-4-search) and follow the instructions to install. Then, enter the path your `gpt_4_search.py` file in `config.py`.

- [EvAnhaodong's fork](https://github.com/EvAnhaodong/gpt-4-search) was considered but was too bloated for a, likely hosted in a low-performance container, Discord bot. Like their fork, however, end-to-end testing will be implemented before adding additional functionality.
- From my testing, this backend was meant to only work on Linux, since the readline module is Linux-only and commonly answering "I don't know" without it mostly for Python responses. As a temporary solution, I removed the import line but a plugin-free backend is also provided.
- This backend also seems to have dubious support for models other than GPT4. While testing with GPT3.5-turbo, it outputs a parsing error when trying to summarize a Google result and output it. Thus, this bot only works with GPT4 for now. The scaffolding is in place to support other models as soon as possible.

The system prompt for the plugins system:
> You are an _[sic]_ helpful and kind assistant to answer questions that can use tools to interact with real world and get access to the latest information. You can call one of the following functions:
In each response, you must start with a function call like `SEARCH(\"something\")` or `PYTHON(\"\"\"1+1\"\"\")`. Don't explain why you use a tool. If you cannot figure out the answer, you say ’I don’t know’. When you are generating answers according to the search result, link your answers to the snippet id like `[1]`, and use the same language as the questioner.

Function prompts:
- **SEARCH:** searches the web, and returns the top snippets, it'll be better if the query string is in english
- **SUMMARIZE:** click into the search result, useful when you want to investigate the detail of the search result
- **PYTHON:** evaluates the code in a python interpreter, wrap code in triple quotes, wrap the answer in `print()`

The user-inputted system prompt would be added before everything else.

## Todo

Another feature that will be implemented is using files (plaintext and PDFs/DOCX/etc.) as context, leveraging Discord's file upload feature and support for direct links and a common filehosting service like Google Drive. The free user filesize limit shouldn't be an issue in this context, however.
Lastly, a streaming solution will be implemented.

- code execution security
- add grants
- user-specific api keys
- streaming
- end-to-end testing

## Usage

If you are using any GPT4 model, the plugins will be enabled by default if `--fallback` is not present. Similarly, GPT3 models will default to fallback if `--plugins` is not present.

- `/setting` resets the channel's settings
- `/setting <model/prompt>` prints the channel's model/prompt
- `/setting model <model_name>` changes the model to `gpt-4`, `gpt-3.5-turbo`, etc.
- `/setting prompt <system_prompt>` changes the system prompt

Then, just talk in any of the ChatGPT-enabled channels/threads and FeverGPT will reply. If you'd like to send a message in that context without a response, prepend it with a backslash:
- `/ This sentence will be ignored by the bot.`

**Scanner:** If you upload and send a PDF file or send a website link directly, a section-by-section summary will be replied.
**Backend:** Google searching and code synthesis will be used to answer your internet-based or math questions, for example.

## Configuration

Make a folder named data in the project folder.
Rename to `config.py.example` to `config.py` and open it with any text editor, like Notepad. Then, enable Developer Mode in Discord and enter the information.

Note: This backend is not optimized for code generation and should not be used for this purpose. The Python functionality is designed for programmatically solving mathematical problems or similar tasks, as GPT may not provide the required precision for these operations.

Adding a new user-level bot setting: 
- Add config command to setting()
- Add default val to DEFAULT{}
- Add functionality to maybe on_message()
- Add to # get channel settings
- Add to COMMANDS

retain empty channel data fields not set as default to differentiate when changing defaults
stop checking messages if reached first
make plugin/fallback flags into channel data and vice versa