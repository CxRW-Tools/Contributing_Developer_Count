import requests
import csv
import argparse
import json
import concurrent.futures
import time
from datetime import datetime, timedelta
import logging
import traceback
import unicodedata

try:
    from tqdm import tqdm
    tqdm_available = True
except ImportError:
    tqdm_available = False
    print("Consider installing tqdm for progress bar: 'pip install tqdm'")

# Constants
DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_TOKEN = ""  # Replace with a default GitHub personal access token if desired
ERRORS_WARNINGS = False

LOG_FILE = "github_contributor_count.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Log debug messages
# Expected types are INFO, ERROR, and WARNING
def log(message, log_type="DEBUG", debug=True):
    global ERRORS_WARNINGS

    # Normalize the message to handle Unicode issues
    try:
        normalized_message = unicodedata.normalize("NFKD", message).encode("ascii", "ignore").decode()
    except Exception as e:
        normalized_message = f"Failed to normalize message: {e}"

    # Normalize log_type and set ERRORS_WARNINGS flag if needed
    log_type = log_type.upper()
    if log_type in ["ERROR", "WARNING"]:
        ERRORS_WARNINGS = True

    # Log the message to the log file
    try:
        if log_type == "ERROR":
            logging.error(normalized_message)
        elif log_type == "WARNING":
            logging.warning(normalized_message)
        elif log_type == "INFO":
            logging.info(normalized_message)
        else:  # Default to DEBUG
            logging.debug(normalized_message)
    except Exception as e:
        # Handle potential logging errors
        logging.error(f"Failed to log message: {e}")

    # Print debug messages to the console if debug is enabled
    if debug:
        print(f"[{log_type}] {normalized_message}")


# Determine if a commit is from a bot
def is_bot(commit):
    # Check the outer `author` field
    author = commit.get("author")
    if author:
        commit_author_type = author.get("type", "")
        if commit_author_type == "Bot":
            return True

        username = author.get("login", "").lower()
        if username.endswith("[bot]"):
            return True

    # Check the inner `commit.author` metadata
    commit_author = commit.get("commit", {}).get("author", {})
    email = commit_author.get("email", "").lower()
    if email.endswith("[bot]"):
        return True

    return False

# Process commits and extract contributors
def process_commits_and_contributors(commits, repo, debug):
    contributors = {}
    bots = {}

    for commit in commits:
        author = commit.get("commit", {}).get("author", {})
        if not author:
            log(f"Skipping commit with no author metadata: {json.dumps(commit, indent=4)}", "INFO", debug)
            continue

        email = author.get("email", "N/A").lower()
        name = author.get("name", "N/A")

        if is_bot(commit):
            if email not in bots:
                log(f"Contributor {name} ({email}) to {repo} is a bot", "INFO", debug)
                bots[email] = True
            continue

        if email not in contributors:
            log(f"Adding {name} ({email}) as contributor to {repo}", "INFO", debug)
            contributors[email] = {
                "name": name,
                "email": email,
                "last_commit": author.get("date", "N/A"),
            }

    return contributors

# Fetch all commits for a repository
def fetch_commits_for_repo(owner, repo, since_date, token, api_url, debug, max_retries=5):
    headers = {"Authorization": f"token {token}"}
    url = f"{api_url}/repos/{owner}/{repo}/commits"
    params = {"since": since_date, "per_page": 100}
    
    all_commits = []
    retry_attempts = 0

    while url:
        try:
            log(f"Fetching commits for {owner}/{repo} with URL: {url}", "INFO", debug)
            response = requests.get(url, headers=headers, params=params, timeout=10)

            # Check for response status and handle specific errors
            if response.status_code == 404:
                log(f"Repository {owner}/{repo} not found (404). Skipping.", "WARNING", debug)
                break
            elif response.status_code == 403:
                # Handle rate limiting with backoff
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
                wait_time = max(0, reset_time - int(time.time()))

                # Convert wait_time to formatted minutes and seconds
                wait_time_minutes, wait_time_seconds = divmod(wait_time, 60)
                formatted_wait_time = f"{wait_time_minutes}m{wait_time_seconds:02d}s"

                # Calculate expected completion time
                expected_completion_time = datetime.now() + timedelta(seconds=wait_time)
                formatted_completion_time = expected_completion_time.strftime("%H:%M")

                log(f"Rate limit exceeded for {owner}/{repo}. Retrying in {wait_time} seconds...", "WARNING", debug)
                if not debug and tqdm_available:
                    tqdm.write(f"[WARNING] Rate limit exceeded. Expected completion: {formatted_completion_time}...")
                time.sleep(wait_time + 3)
                continue

            # Raise an exception for other non-success statuses
            response.raise_for_status()

            # Process commits
            commits = response.json()
            all_commits.extend(commits)

            log(f"Fetched {len(commits)} commits for {owner}/{repo}. Total so far: {len(all_commits)}", "INFO", debug)

            # Reset retries after a successful request
            retry_attempts = 0

            # Check for next page in the `Link` header
            if "Link" in response.headers:
                links = parse_link_header(response.headers["Link"])
                url = links.get("next")
            else:
                url = None

        except requests.exceptions.Timeout:
            retry_attempts += 1
            if retry_attempts > max_retries:
                log(f"Max retries exceeded for {owner}/{repo}. Skipping.", "WARNING", debug)
                break

            backoff_time = 2 ** retry_attempts
            log(f"Request timed out for {owner}/{repo}. Retrying in {backoff_time} seconds...", "WARNING", debug)
            if not debug and tqdm_available:
                tqdm.write(f"[WARNING] Timeout for {owner}/{repo}. Retrying in {backoff_time} seconds...")
            time.sleep(backoff_time)
            continue

        except requests.exceptions.RequestException as e:
            log(f"Error fetching commits for {owner}/{repo}: {e}", "WARNING", debug)
            break

    return all_commits

# Parse the GitHub link header
def parse_link_header(link_header):
    links = {}
    for part in link_header.split(","):
        section = part.split(";")
        url = section[0].strip()[1:-1]  # Remove < and >
        rel = section[1].strip().split("=")[1].strip('"')
        links[rel] = url
    return links

# Process a single repository
def process_single_repository(repo, since_date, token, api_url, debug):
    owner, repo_name = repo.split("/")
    log(f"Processing repository: {repo}", "INFO", debug)
    
    # Fetch all commits for the repository
    commits = fetch_commits_for_repo(owner, repo_name, since_date, token, api_url, debug)
    
    # Process commits to deduplicate contributors
    contributors = process_commits_and_contributors(commits, repo, debug)
    
    # Prepare contributor results
    results = []
    for email, details in contributors.items():
        results.append({
            "repo": f"{owner}/{repo_name}",
            "email": details["email"],
            "name": details["name"],
            "last_commit": details["last_commit"],
        })
    
    return results

# Process repositories and generate CSV
def process_repositories(repo_file, since_days, token, api_url, output_file, debug):
    since_date = (datetime.utcnow() - timedelta(days=since_days)).isoformat() + "Z" if since_days else None
    log(f"Using cutoff date: {since_date}", "INFO", debug)
    all_contributors = []
    repo_contributor_map = {}

    log(f"Reading repositories from file: {repo_file}", "INFO", debug)
    with open(repo_file, "r", encoding="utf-8") as file:
        repositories = [line.strip() for line in file if line.strip()]
    log(f"Processing {len(repositories)} repositories", "INFO", debug)

    # Initialize progress bar if tqdm is available and debugging is disabled
    progress_bar = None
    if tqdm_available and not debug:
        progress_bar = tqdm(total=len(repositories), desc="Processing repositories")

    # Process repositories concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Map repositories to futures
        future_to_repo = {
            executor.submit(process_single_repository, repo, since_date, token, api_url, debug): repo
            for repo in repositories
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_repo):
            repo = future_to_repo[future]  # Get the repository associated with this future
            try:
                result = future.result()
                all_contributors.extend(result)

                # Track unique contributors per repository
                unique_emails = {contributor["email"] for contributor in result}
                repo_contributor_map[repo] = len(unique_emails)

            except Exception as e:
                log(f"Error processing repository {repo}: {e}", "ERROR", debug)
                log(f"{traceback.format_exc()}", "TRACEBACK", debug)
            
            # Update progress bar if available
            if progress_bar:
                progress_bar.update(1)

    # Close the progress bar if available
    if progress_bar:
        progress_bar.close()

    # Write contributors to the CSV
    log(f"Writing results to CSV: {output_file}", "INFO", debug)
    with open(output_file, mode="w", newline="", encoding="utf-8") as file:
        headers = {
            "repo": "Repository",
            "email": "Contributor Email",
            "name": "Contributor Name",
            "last_commit": "Last Commit Timestamp",
        }

        writer = csv.DictWriter(file, fieldnames=headers.keys())
        writer.writerow(headers)
        writer.writerows(all_contributors)

    # Calculate deduplicated total contributors
    log(f"Calculating summary information", "INFO", debug)
    total_unique_contributors = len({contributor["email"] for contributor in all_contributors})

    # Print contributor summary to console
    DEFAULT_WIDTH = 40
    MAX_WIDTH = 80
    max_repo_length = max((len(repo) for repo in repo_contributor_map.keys()), default=DEFAULT_WIDTH)
    repo_column_width = min(max(DEFAULT_WIDTH, max_repo_length), MAX_WIDTH)

    # Print header
    print("\nContributor Summary:")
    print(f"{'Repository':<{repo_column_width}} {'Unique Contributors':<20}")
    print("-" * (repo_column_width + 22))

    # Print each repository and its unique contributors
    for repo, count in repo_contributor_map.items():
        print(f"{repo:<{repo_column_width}} {count:<20}")
    
    # Print total row
    print("-" * (repo_column_width + 22))
    print(f"{'Total':<{repo_column_width}} {total_unique_contributors:<20}")

    print(f"\nDetailed data written to {output_file}")

# Main
def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub contributors and their last commit info.")
    parser.add_argument("repo-file", help="Path to the text file containing repositories in 'owner/repo' format.")
    parser.add_argument("--days", type=int, default=90, help="Number of days to look back for contributions (default: 90).")
    parser.add_argument("--token", type=str, default=DEFAULT_TOKEN, help="GitHub personal access token (optional).")
    parser.add_argument("--api-url", type=str, default=DEFAULT_GITHUB_API_URL, help="GitHub API URL (optional).")
    parser.add_argument("--output", type=str, default="contributors.csv", help="Output CSV file name (default: contributors.csv).")
    parser.add_argument("--debug", action="store_true", help="Enable debug output.")
    args = parser.parse_args()

    log("Starting process with provided arguments", "INFO", args.debug)

    process_repositories(args.repo_file, args.days, args.token, args.api_url, args.output, args.debug)

    # Check and print a message if there were errors or warnings
    if ERRORS_WARNINGS:
        print("\nProcess completed with errors or warnings. Check the logs for details.")
        log(f"Process completed with errors or warnings.", "INFO", args.debug)
    else:
        log(f"Process completed", "INFO", args.debug)

if __name__ == "__main__":
    main()
