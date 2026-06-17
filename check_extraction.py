from app.core.github_client import GitHubClient
from app.agents.failure_analyzer import _extract_relevant_excerpt

client = GitHubClient(repo_owner='acctofaditya2005', repo_name='Taskhub-api')
run = client.get_latest_failed_run(branch='break/config-missing-secret-key')
jobs = client.get_failed_jobs(run)
log = client.download_job_log(jobs[0])

excerpt = _extract_relevant_excerpt(log)
print('Excerpt length:', len(excerpt))
print('Contains "ValidationError":', 'ValidationError' in excerpt)
print('Contains "SECRET_KEY":', 'SECRET_KEY' in excerpt)
print('Contains "Field required":', 'Field required' in excerpt)
print()
print('--- Full excerpt sent to the model ---')
print(excerpt)