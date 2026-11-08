package supervisor

import (
	"context"
	"encoding/json"
	"errors"
	"os/exec"
	"time"
)

type Reply struct {
	Paused          bool   `json:"paused"`
	State           string `json:"state"`
	JobID           string `json:"job_id"`
	StoreID         string `json:"store_id"`
	Status          string `json:"status"`
	ReceiptID       string `json:"receipt_id,omitempty"`
	CancelRequested bool   `json:"cancel_requested"`
}
type Bridge interface {
	Call(context.Context, string, string, string) (Reply, error)
}
type PythonBridge struct{ Config Config }
type boundedOutput struct {
	data     []byte
	overflow bool
}

func (w *boundedOutput) Write(p []byte) (int, error) {
	n := len(p)
	room := 65536 - len(w.data)
	if len(p) > room {
		w.overflow = true
		p = p[:room]
	}
	w.data = append(w.data, p...)
	return n, nil
}
func (b PythonBridge) Call(ctx context.Context, action, store, job string) (Reply, error) {
	var r Reply
	if !identifier.MatchString(store) || (job != "" && !jobIdentifier.MatchString(job)) {
		return r, errors.New("invalid bridge identity")
	}
	switch action {
	case "status":
		if job != "" {
			return r, errors.New("unexpected job")
		}
	case "run", "receipt", "cancel":
		if job == "" {
			return r, errors.New("missing job")
		}
	default:
		return r, errors.New("invalid bridge action")
	}
	args := []string{"-m", "app.supervisor_bridge", "--action", action, "--store-id", store}
	if job != "" {
		args = append(args, "--job-id", job)
	}
	var cmd *exec.Cmd
	if action == "run" {
		cmd = exec.Command(b.Config.Python, args...)
	} else {
		helperCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
		defer cancel()
		cmd = exec.CommandContext(helperCtx, b.Config.Python, args...)
		cmd.WaitDelay = time.Second
	}
	cmd.Dir = b.Config.ServerDir
	w := &boundedOutput{}
	cmd.Stdout = w
	// Collector runs never use CommandContext: request job-specific cancellation
	// and retain the store claim. Only read/control helpers have kill deadlines.
	if err := ctx.Err(); err != nil {
		return r, err
	}
	err := cmd.Run()
	if w.overflow {
		return r, errors.New("bridge output exceeds limit")
	}
	if e := json.Unmarshal(w.data, &r); e != nil {
		return Reply{}, errors.New("invalid bridge response")
	}
	if action == "status" {
		var status struct {
			Paused *bool  `json:"paused"`
			State  string `json:"state"`
		}
		if json.Unmarshal(w.data, &status) != nil || status.Paused == nil || (status.State != "enabled" && status.State != "pausing" && status.State != "paused") || (status.Paused != nil && *status.Paused != (status.State != "enabled")) {
			return Reply{}, errors.New("missing authoritative pause status")
		}
	}
	if r.ReceiptID != "" && !jobIdentifier.MatchString(r.ReceiptID) {
		return Reply{}, errors.New("invalid receipt reference")
	}
	if (action == "run" || action == "receipt") && (r.Status == "complete" || r.Status == "paused" || r.Status == "failed") && r.ReceiptID == "" {
		return Reply{}, errors.New("missing final receipt reference")
	}
	if action != "status" && (r.JobID != job || r.StoreID != store) {
		return Reply{}, errors.New("bridge identity mismatch")
	}
	if action == "cancel" && !r.CancelRequested {
		return Reply{}, errors.New("cancel not acknowledged")
	}
	if action == "run" || action == "receipt" {
		switch r.Status {
		case "complete", "paused", "failed", "running", "unknown":
		default:
			return Reply{}, errors.New("invalid bridge status")
		}
	}
	if err != nil && !(action == "run" && (r.Status == "failed" || r.Status == "paused")) {
		return r, errors.New("bridge execution failed")
	}
	return r, nil
}
