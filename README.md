
# Codeprinter

**Codeprinter** is a local tool designed for quickly selecting and packaging files from GitHub and local repositories, allowing for easy copy/pasting with chat-based LLMs.

This was made possible thanks to Abin Thomas open-sourcing [repo2txt](https://github.com/abinthomasonline/repo2txt) as a base to build on, so I am open-sourcing this to pass it forward. Thank you, Abin! My main change was converting the app to be a uv flask executable app, and making local mode work by just passing a local path instead of a zip file.

NOTE: The local path only works if the filesystem is in same location as the code running. So when I am coding on a Windows using WSL, I can only pass local WSL repos, and when coding on Windows I can pass local Windows repos.

## Quick Start

To run Codeprinter:
1. Clone this repository:
   ```bash
   git clone https://github.com/ChristianCasazza/codeprinter
   ```
2. Start the application using `uv`:
   ```bash
   uv run codeprinter/app.py
   ```

Thanks to `uv`, no virtual environment (venv) setup is required because the package dependencies are already included within the script.

### Installing `uv`
If you don’t already have `uv` installed, you can add it via pip:
```bash
pip install uv
```
For more details, refer to the [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

## Configuration

### Excluding Folders
within the `app.py`, you’ll find the `skip_dirs` variable, which lists directories to exclude from the UI. By default, it includes:
- `.venv`
- `node_modules`
- `.git`
- `.vscode`
- `.evidence`
- `target`

Edit this list as needed to customize which folders are skipped. I designed this to be quick and easy to edit so it can be customized for particular repos without much investment. 

### Allowed File Types
To configure the file types displayed in the UI, edit the file type filters at the bottom of `index.html`. This allows you to control the file extensions visible in the application(such as allowing .py, .js, and .sql files to show but not .lock or .log)

### Working with Github
Passing public github repo links will work in Github mode the same way as local mode.

However, especially large repos might be rate limited by Github and fail. This can be mitgated by providing a Github access token.

Github mode also works with your own personal private repos. I would recommend just creating the classic Github PAT with the repo permissions instead of creating one of the new fine-grained tokens. Github PATs are a fair bit simpler to set up, and still work with Codeprinter.

Private repos are currently only supported if you are the owner of the repo, private repos that are shared with you but you do not own will not work.
In this scenario, I would suggest forking the private repo into your own account and using that. The correct permissions needed to make this work with shared private repos can probably be figured out eventually. 


## Contributing
Feel free to submit issues or feature requests via the GitHub repository.

Best place to contact me is sending me a DM on X at [@CasazzaNY](https://x.com/CasazzaNY)

---
**Happy coding!**
