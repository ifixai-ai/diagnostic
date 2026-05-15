"""Typed exceptions for the evaluation pipeline.

These exceptions exist to distinguish *configuration* failures (the run
cannot produce a score because something was not wired up) from
*runtime* judge failures (the judge ran but could not deliver a
verdict). Configuration failures must surface to operators as ERROR;
runtime judge failures stay INCONCLUSIVE.
"""


class JudgePipelineRequiredError(RuntimeError):
    """A benchmark required the analytic judge pipeline but none was configured.

    Raised pre-flight by judge-dependent runners and by the evaluation
    pipeline when invoked without a judge or rubric. The harness maps
    this to ``TestStatus.ERROR`` (a configuration failure), distinct
    from the ``INCONCLUSIVE`` status used for runs where the judge ran
    but could not produce a score.
    """

    def __init__(self, test_id: str, reason: str) -> None:
        super().__init__(f"{test_id}: judge pipeline required ({reason})")
        self.test_id = test_id
        self.reason = reason
