"""
LangGraph wiring for the CI/CD failure investigation pipeline.

The graph is intentionally a straight line for now (Agent 1 -> 2 ->
3 -> 4 -> 5 -> 6), since the current failure modes don't yet need
branching. The natural places branching/looping would earn its keep
later: skip Agent 3 (repo investigation) entirely for Dependency
Failures where the fix is almost always just the manifest file; loop
back to Agent 2 with a different prompt if confidence is very low;
or short-circuit before Agent 6 (already partially handled inside
that agent via the confidence threshold).

Modeled as a graph rather than a plain function chain specifically
so those branching points can be added later without restructuring
the whole pipeline -- LangGraph's conditional edges are built for
exactly this kind of incremental complexity growth.
"""

from langgraph.graph import END, StateGraph

from app.agents.failure_analyzer import run_failure_analyzer
from app.agents.fix_recommender import run_fix_recommender
from app.agents.issue_creator import run_issue_creator
from app.agents.report_generator import run_report_generator
from app.agents.repo_investigator import run_repo_investigator
from app.core.github_client import GitHubClient
from app.models.state import InvestigationState


def build_graph(
    github_client: GitHubClient,
    dry_run_issue_creation: bool = True,
    include_commit_message_in_classification: bool = False,
):
    """
    Builds and compiles the LangGraph pipeline. Agent 1 (Workflow
    Monitor) is NOT part of this graph -- it runs separately to
    produce the initial InvestigationState, since it needs different
    inputs (repo/branch/run_id) than the rest of the pipeline, which
    just needs the state object to keep flowing forward.

    github_client is closed over here (rather than passed through
    state) because Agents 3 and 6 need live API access, not just
    data -- passing a client object through a Pydantic state model
    would be awkward and isn't needed by the eval harness anyway.

    include_commit_message_in_classification defaults to False --
    see app.agents.failure_analyzer._build_user_prompt for why.
    """
    graph = StateGraph(InvestigationState)

    graph.add_node(
        "failure_analyzer",
        lambda s: run_failure_analyzer(
            s, include_commit_message=include_commit_message_in_classification
        ),
    )
    graph.add_node("repo_investigator", lambda s: run_repo_investigator(s, github_client))
    graph.add_node("fix_recommender", run_fix_recommender)
    graph.add_node("report_generator", run_report_generator)
    graph.add_node(
        "issue_creator",
        lambda s: run_issue_creator(s, github_client, dry_run=dry_run_issue_creation),
    )

    graph.set_entry_point("failure_analyzer")
    graph.add_edge("failure_analyzer", "repo_investigator")
    graph.add_edge("repo_investigator", "fix_recommender")
    graph.add_edge("fix_recommender", "report_generator")
    graph.add_edge("report_generator", "issue_creator")
    graph.add_edge("issue_creator", END)

    return graph.compile()
