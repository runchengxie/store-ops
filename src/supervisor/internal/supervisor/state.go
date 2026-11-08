package supervisor

import (
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
)

type Job struct {
	ID              string `json:"job_id"`
	StoreID         string `json:"store_id"`
	Period          int64  `json:"period"`
	Status          string `json:"status"`
	Started         int64  `json:"started,omitempty"`
	Finished        int64  `json:"finished,omitempty"`
	ReceiptID       string `json:"receipt_id,omitempty"`
	CancelRequested bool   `json:"cancel_requested,omitempty"`
}
type State struct {
	Version int              `json:"version"`
	Next    map[string]int64 `json:"next"`
	Jobs    []Job            `json:"jobs"`
}

func load(dir string) (State, error) {
	s := State{Version: 1, Next: map[string]int64{}, Jobs: []Job{}}
	data, err := readBounded(filepath.Join(dir, "state.json"), 2<<20)
	if os.IsNotExist(err) {
		return s, nil
	}
	if err != nil {
		return s, err
	}
	var wire struct {
		Version *int             `json:"version"`
		Next    map[string]int64 `json:"next"`
		Jobs    *[]Job           `json:"jobs"`
	}
	if err = decode(data, &wire); err != nil {
		return s, err
	}
	if wire.Version == nil || wire.Next == nil || wire.Jobs == nil {
		return s, errors.New("missing state fields")
	}
	s = State{Version: *wire.Version, Next: wire.Next, Jobs: *wire.Jobs}
	if s.Version != 1 || s.Next == nil || len(s.Next) > 100 || len(s.Jobs) > 1000 {
		return s, errors.New("invalid state")
	}
	seen := map[string]bool{}
	for _, j := range s.Jobs {
		if j.Period < 1 || j.Started < 0 || j.Finished < 0 || (j.ReceiptID != "" && !jobIdentifier.MatchString(j.ReceiptID)) || !jobIdentifier.MatchString(j.ID) || !identifier.MatchString(j.StoreID) || seen[j.ID] {
			return s, errors.New("invalid job identity")
		}
		seen[j.ID] = true
		if (j.Status == "complete" || j.Status == "paused" || j.Status == "failed") && (!jobIdentifier.MatchString(j.ReceiptID) || j.Started < 1 || j.Finished < 1) {
			return s, errors.New("invalid terminal job")
		}
		if (j.Status == "running" || j.Status == "needs_review") && j.Started < 1 {
			return s, errors.New("invalid started job")
		}
		switch j.Status {
		case "queued", "running", "needs_review", "complete", "paused", "failed":
		default:
			return s, errors.New("invalid job state")
		}
	}
	for k, v := range s.Next {
		if !identifier.MatchString(k) || v < 0 {
			return s, errors.New("invalid schedule")
		}
	}
	return s, nil
}
func save(dir string, s State) error {
	s.Version = 1
	data, err := json.Marshal(s)
	if err != nil {
		return err
	}
	f, err := os.CreateTemp(dir, ".state-*")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if err = f.Chmod(0600); err == nil {
		_, err = f.Write(data)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	return replace(name, filepath.Join(dir, "state.json"))
}

// PrintStatus reads the last atomic snapshot without acquiring the writer lock.
// In-flight entries are reported as recorded, never inferred to be successful.
func PrintStatus(c Config, w io.Writer) error {
	s, e := load(c.DataDir)
	if e != nil {
		return e
	}
	return json.NewEncoder(w).Encode(s)
}
