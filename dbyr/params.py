"""Protocol parameters: deadlines, floors and fixed lists the checks apply.

Operator-set; the defaults below are the paper's. Changing one changes what lodges.

    NOTICE_HOURS            interim ExceptionNotice deadline after detection
    NOTIFY_HOURS            third-party notification deadline after detection
    MAX_EVAL_DAYS           longest window one evaluation Intent may cover
    CORE_KINDS_T4           event kinds a safeguards-off filing must give a pausing criterion
    PAUSING                 required actions that count as pausing
    SAFEGUARDS              production safeguards every Intent states the state of
    REPORTABLE              event kinds that always need an ExceptionNotice
    MIN_SAMPLE              a sampled monitor below this rate observes nothing
    INTAKE_DAYS             an Intent is filed at least this long before the run starts
    RETENTION_FLOOR_MONTHS  shortest retention after closeout
    CLOSEOUT_EVERY_DAYS     longest period one Closeout may cover
    OBSERVERS               which monitor kinds can observe which event kinds
"""

NOTICE_HOURS = 72
NOTIFY_HOURS = 72
MAX_EVAL_DAYS = 31
CORE_KINDS_T4 = ("sandbox_escape", "privilege_escalation", "inter_agent_comms", "third_party_compromise")
PAUSING = ("pause", "pause_and_review", "halt_and_amend_intent")

SAFEGUARDS = ("model_output_filters", "refusal_behaviour", "per_episode_reset", "network_isolation",
              "identity_separation", "least_privilege_access")
REPORTABLE = ("sandbox_escape", "undeclared_surface_use", "inter_agent_comms", "credential_misuse",
              "privilege_escalation", "remote_code_execution", "agent_induced_outage", "third_party_compromise",
              "environment_tampering", "access_boundary_breach", "data_exposure", "integrity_incident")
MIN_SAMPLE = 0.01          # a sampled monitor below this rate observes nothing for these checks
INTAKE_DAYS = 3            # an Intent must be filed this long before the run starts
RETENTION_FLOOR_MONTHS = 12
CLOSEOUT_EVERY_DAYS = 30

# Which declared monitor kinds can observe which event kinds. An event kind with
# no observer is visible only by accident. Outages and third-party compromises
# are observable without a dedicated monitor (operations alarms; external report).
OBSERVERS = {
    "environment_tampering": {"environment_integrity_check", "write_audit", "reward_seeking_monitor", "trajectory_review"},
    "access_boundary_breach": {"access_log_review", "trajectory_review"},
    "data_exposure": {"access_log_review", "write_audit", "trajectory_review"},
    "integrity_incident": {"write_audit", "trajectory_review"},
    "sandbox_escape": {"network_alerting", "trajectory_review"},
    "undeclared_surface_use": {"write_audit", "environment_integrity_check", "trajectory_review"},
    "inter_agent_comms": {"inter_agent_message_monitor", "trajectory_review"},
    "credential_misuse": {"access_log_review", "environment_integrity_check"},
    "privilege_escalation": {"access_log_review", "environment_integrity_check"},
    "remote_code_execution": {"environment_integrity_check", "access_log_review", "trajectory_review"},
    "agent_induced_outage": None,  # always observable
    "third_party_compromise": None,  # observable by external report
    "monitor_alert": "any",
}
