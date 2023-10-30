# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from abc import abstractmethod
from logging import Logger
from typing import List, Optional, Set

from ax.core.base_trial import TrialStatus

from ax.core.experiment import Experiment
from ax.utils.common.base import Base
from ax.utils.common.logger import get_logger
from ax.utils.common.serialization import SerializationMixin

logger: Logger = get_logger(__name__)


class TransitionCriterion(Base, SerializationMixin):
    """
    Simple class to descibe a condition which must be met for a GenerationStrategy
    to move to its next GenerationNode.

    Args:
        transition_to: The name of the GenerationNode the GenerationStrategy should
            transition to when this criterion is met.
    """

    _transition_to: Optional[str] = None

    def __init__(self, transition_to: Optional[str] = None) -> None:
        self._transition_to = transition_to

    @property
    def transition_to(self) -> Optional[str]:
        """The name of the next GenerationNode after this TransitionCriterion is
        completed. Warns if unset.
        """
        if self._transition_to is None:
            logger.warning("No transition_to specified on this TransitionCriterion")

        return self._transition_to

    @abstractmethod
    def is_met(
        self, experiment: Experiment, trials_from_node: Optional[Set[int]] = None
    ) -> bool:
        pass


class MinimumTrialsInStatus(TransitionCriterion):
    """
    Simple class to decide if the number of trials of a given status in the
    GenerationStrategy experiment has reached a certain threshold.
    """

    # TODO: @mgarrard rename to MinTrials and expand functionality to mirror
    #  `MaxTrials` after legacy usecases are updated.
    def __init__(
        self,
        statuses: List[TrialStatus],
        threshold: int,
        transition_to: Optional[str] = None,
    ) -> None:
        self.statuses = statuses
        self.threshold = threshold
        super().__init__(transition_to=transition_to)

    def is_met(
        self, experiment: Experiment, trials_from_node: Optional[Set[int]] = None
    ) -> bool:
        """Checks if the MinimumTrialsInStatus criterion is met.
        Args:
            experiment: The experiment associated with this GenerationStrategy.
            trials_from_node: A set containing the indices of trials that were
                generated from this GenerationNode.
        """
        exp_trials_with_statuses = set()
        for status in self.statuses:
            exp_trials_with_statuses = exp_trials_with_statuses.union(
                experiment.trial_indices_by_status[status]
            )

        # Trials from node should not be none for any new GenerationStrategies
        if trials_from_node is None:
            logger.warning(
                "trials_from_node is None, will check threshold on experiment level.",
            )
            return len(exp_trials_with_statuses) >= self.threshold
        return (
            len(trials_from_node.intersection(exp_trials_with_statuses))
            >= self.threshold
        )

    def __repr__(self) -> str:
        """Returns a string representation of MinimumTrialsInStatus."""
        return (
            f"{self.__class__.__name__}(statuses={self.statuses}, "
            f"threshold={self.threshold}, transition_to='{self.transition_to}')"
        )


class MaxTrials(TransitionCriterion):
    """
    Simple class to enforce a maximum threshold for the number of trials generated
    by a specific GenerationNode.

    Args:
        threshold: the designated maximum number of trials
        enforce: whether or not to enforce the max trial constraint
        only_in_status: optional argument for specifying only checking trials with
            this status. If not specified, all trial statuses are counted.
    """

    def __init__(
        self,
        threshold: int,
        enforce: bool,
        only_in_status: Optional[TrialStatus] = None,
        transition_to: Optional[str] = None,
    ) -> None:
        self.threshold = threshold
        self.enforce = enforce
        self.only_in_status = only_in_status
        super().__init__(transition_to=transition_to)

    def is_met(
        self, experiment: Experiment, trials_from_node: Optional[Set[int]] = None
    ) -> bool:
        """Checks if the MaxTrials criterion is met.
        Args:
            experiment: The experiment associated with this GenerationStrategy.
            trials_from_node: A set containing the indices of trials that were
                generated from this GenerationNode.
        """
        if self.enforce:
            # Trials from node should not be none for any new GenerationStrategies
            if trials_from_node is None:
                logger.warning(
                    "trials_from_node is None, will check threshold on"
                    + " experiment level.",
                )
                if self.only_in_status is not None:
                    return (
                        len(experiment.trial_indices_by_status[self.only_in_status])
                        >= self.threshold
                    )
                return len(experiment.trials) >= self.threshold
            if self.only_in_status is not None:
                return (
                    len(
                        trials_from_node.intersection(
                            experiment.trial_indices_by_status[self.only_in_status]
                        )
                    )
                    >= self.threshold
                )
            return len(trials_from_node) >= self.threshold
        return True

    def __repr__(self) -> str:
        """Returns a string representation of MaxTrials."""
        return (
            f"{self.__class__.__name__}(threshold={self.threshold}, "
            f"enforce={self.enforce}, only_in_status={self.only_in_status}, "
            f"transition_to='{self.transition_to}')"
        )


class MinimumPreferenceOccurances(TransitionCriterion):
    """
    In a preference Experiment (i.e. Metric values may either be zero for No and
    nonzero for Yes) do not transition until a minimum number of both Yes and No
    responses have been received.
    """

    def __init__(
        self, metric_name: str, threshold: int, transition_to: Optional[str] = None
    ) -> None:
        self.metric_name = metric_name
        self.threshold = threshold
        super().__init__(transition_to=transition_to)

    def is_met(
        self, experiment: Experiment, trials_from_node: Optional[Set[int]] = None
    ) -> bool:
        # TODO: @mgarrard replace fetch_data with lookup_data
        data = experiment.fetch_data(metrics=[experiment.metrics[self.metric_name]])

        count_no = (data.df["mean"] == 0).sum()
        count_yes = (data.df["mean"] != 0).sum()

        return count_no >= self.threshold and count_yes >= self.threshold

    def __repr__(self) -> str:
        """Returns a string representation of MinimumPreferenceOccurances."""
        return (
            f"{self.__class__.__name__}(metric_name='{self.metric_name}', "
            f"threshold={self.threshold}, transition_to={self.transition_to})"
        )
