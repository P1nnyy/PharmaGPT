import os
import requests
import json
import google.generativeai as genai

# Setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")

def get_pr_diff(owner, repo, pr_number):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = requests.get(url, headers=headers)
    return response.text

def post_pr_comment(owner, repo, pr_number, body):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"body": body}
    requests.post(url, headers=headers, data=json.dumps(data))

def main():
    if not all([GITHUB_TOKEN, GOOGLE_API_KEY, GITHUB_REPOSITORY, GITHUB_EVENT_PATH]):
        print("Missing environment variables.")
        return

    # Load PR event data
    with open(GITHUB_EVENT_PATH, "r") as f:
        event_data = json.load(f)

    pr_number = event_data.get("pull_request", {}).get("number")
    if not pr_number:
        print("Not a pull request event.")
        return

    owner, repo = GITHUB_REPOSITORY.split("/")
    diff = get_pr_diff(owner, repo, pr_number)

    if not diff:
        print("No diff found.")
        return

    # Initialize Gemini
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

    prompt = f"""
    You are an expert software engineer reviewing a pull request for a project called "PharmaGPT".
    Focus on:
    1. Potential bugs or security vulnerabilities.
    2. Consistency with existing patterns (FastAPI, Neo4j, LangChain).
    3. Performance and readability.

    Here is the PR Diff:
    ```diff
    {diff[:30000]} # Truncate if very long
    ```

    Provide your review as a concise GitHub comment. Use markdown.
    Start with a summary then use bullet points for specific feedback.
    If the changes look great, just say "LGTM! 🚀" with a short nice message.
    """

    response = model.generate_content(prompt)
    review_body = response.text

    # Post comment back to GitHub
    post_pr_comment(owner, repo, pr_number, f"### 🤖 AI Code Review\n\n{review_body}")
    print("AI Review posted successfully.")

if __name__ == "__main__":
    main()
