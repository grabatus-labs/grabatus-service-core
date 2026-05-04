# Common alert policies that every Grabatus computational service
# inherits via this module:
#
#   1. receiver_error_rate    — 5xx rate from the shared receiver,
#                               warning level (the receiver itself
#                               failing means every downstream service
#                               is silently broken).
#   2. unauthorized_uri        — security alert: the runner rejected
#                                a URI as not-allowed. Single
#                                occurrence is critical, because it
#                                indicates either misconfiguration
#                                of the registry or active probing.
#
# Per-service policies (worker p99 latency, DLQ ingestion, webhook
# failures) live in each service's repo. Putting them in a per-service
# module keeps the operational ownership clear: whoever pages on the
# alert is whoever maintains the service it tracks.

resource "google_monitoring_alert_policy" "receiver_error_rate" {
  project      = var.project
  display_name = "[${var.environment}] receiver 5xx rate above ${var.error_rate_threshold}/s"
  combiner     = "OR"

  conditions {
    display_name = "5xx response rate"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "resource.label.service_name = \"${var.receiver_service_name}\"",
        "metric.type = \"run.googleapis.com/request_count\"",
        "metric.label.response_code_class = \"5xx\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = var.error_rate_threshold
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy {
    auto_close = var.auto_close_duration
  }

  notification_channels = var.notification_channels
  severity              = "WARNING"

  documentation {
    content   = <<-EOT
      The shared receiver is returning 5xx more often than expected.
      Investigate via:

        gcloud run services logs read ${var.receiver_service_name} \
          --region us-east1 \
          --filter 'severity>=ERROR'

      Likely causes:
      - downstream Cloud Run Job is missing (registry drift),
      - SERVICE_SECRET_KEY rotated but receiver not redeployed,
      - WIF token expired or pool config changed.
    EOT
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "unauthorized_uri" {
  project      = var.project
  display_name = "[${var.environment}] unauthorized URI rejection (security)"
  combiner     = "OR"

  conditions {
    display_name = "any UnauthorizedUriError logged"

    condition_matched_log {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "jsonPayload.error_code = \"unauthorized_uri\"",
      ])
    }
  }

  alert_strategy {
    auto_close = var.auto_close_duration

    notification_rate_limit {
      period = "300s"
    }
  }

  notification_channels = var.notification_channels
  severity              = "CRITICAL"

  documentation {
    content   = <<-EOT
      A runner rejected a URI as not-allowed. This is either a real
      security event (someone is probing) or registry drift.

      Investigate the request_id in the log entry that triggered this
      alert; cross-reference with the originating Pub/Sub message.
    EOT
    mime_type = "text/markdown"
  }
}
