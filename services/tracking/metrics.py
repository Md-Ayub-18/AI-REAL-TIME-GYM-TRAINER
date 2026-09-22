import streamlit as st
import time

from services.config.workout_config import METRICS_FIELDS
from services.persistence.exercise_repository import add_exercise


def sync_metrics_update(context):

    if not context or not hasattr(context, "state") or not context.state.playing:
        return

    processor = getattr(context, "video_processor", None)

    if not processor:
        return

    exercise = st.session_state.get("exercise_type")

    if not exercise:
        return

    processor.set_exercise(exercise)

    latest_metrics = processor.get_latest_metrics()

    if not latest_metrics:
        return

    # ---------------------------------------------------------
    # UPDATE REP COUNT
    # ---------------------------------------------------------

    reps = latest_metrics.get("reps", 0)

    if reps is None:
        reps = 0

    st.session_state.reps = reps

    # ---------------------------------------------------------
    # UPDATE EXERCISE METRICS
    # ---------------------------------------------------------

    fields = METRICS_FIELDS.get(exercise)

    if not fields:
        return

    for key, default in fields.items():
        st.session_state[key] = latest_metrics.get(key, default)

    # ---------------------------------------------------------
    # CALCULATE SETS
    # ---------------------------------------------------------

    reps_per_set = st.session_state.get("reps_per_set", 0)
    target_sets = st.session_state.get("target_sets", 0)

    if reps_per_set > 0 and target_sets > 0:

        sets_completed = reps // reps_per_set
        current_set_reps = reps % reps_per_set

        workout_completed = sets_completed >= target_sets

    else:

        sets_completed = 0
        current_set_reps = 0
        workout_completed = False

    st.session_state.sets_completed = sets_completed
    st.session_state.current_set_reps = current_set_reps
    st.session_state.workout_completed = workout_completed

    # ---------------------------------------------------------
    # AI COACH
    # ---------------------------------------------------------

    voice_pipeline = st.session_state.get("voice_pipeline")

    if voice_pipeline:

        now = time.time()

        last_coach_time = st.session_state.get(
            "last_coach_feedback_time",
            0
        )

        # -----------------------------------------------------
        # SET COMPLETED
        # -----------------------------------------------------

        last_saved_sets = st.session_state.get(
            "last_saved_sets_completed",
            0
        )

        if (
            target_sets > 0
            and reps_per_set > 0
            and sets_completed > last_saved_sets
        ):

            newly_completed = sets_completed - last_saved_sets

            started_at = st.session_state.get(
                "set_cycle_started_at",
                now
            )

            time_taken = now - started_at

            user_id = st.session_state.get("user_id", 0)

            add_exercise(
                user_id,
                exercise,
                newly_completed * reps_per_set,
                newly_completed,
                time_taken
            )

            result = voice_pipeline.process_event(
                event="set_completed",
                exercise=exercise,
                metrics=latest_metrics,
            )

            if result:

                st.session_state.audio_to_play = result[0]
                st.session_state.coach_feedback = result[1]

            st.session_state.set_cycle_started_at = now

            st.session_state.last_saved_sets_completed = (
                sets_completed
            )

            st.session_state.last_coach_feedback_time = now

        # -----------------------------------------------------
        # WORKOUT COMPLETED
        # -----------------------------------------------------

        elif (
            workout_completed
            and not st.session_state.get(
                "last_notified_workout_complete",
                False
            )
        ):

            st.session_state.last_notified_workout_complete = True

            result = voice_pipeline.process_event(
                event="workout_completed",
                exercise=exercise,
                metrics=latest_metrics,
            )

            if result:

                st.session_state.audio_to_play = result[0]
                st.session_state.coach_feedback = result[1]

            st.session_state.last_coach_feedback_time = now

        # -----------------------------------------------------
        # ONGOING AI FORM COACHING
        # -----------------------------------------------------

        elif now - last_coach_time >= 5:

            result = voice_pipeline.process_event(
                event="ongoing_form_check",
                exercise=exercise,
                metrics=latest_metrics,
            )

            if result:

                st.session_state.audio_to_play = result[0]
                st.session_state.coach_feedback = result[1]

                st.session_state.last_coach_feedback_time = now