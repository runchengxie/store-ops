package supervisor

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Engine struct {
	persisted       []byte
	mu              sync.Mutex
	closed          bool
	config          Config
	bridge          Bridge
	state           State
	file            *os.File
	active          map[string]bool
	pauseCheckAfter map[string]time.Time
	wg              sync.WaitGroup
	fatal           error
}

func Open(c Config, b Bridge) (*Engine, error) {
	if err := c.Validate(); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(c.DataDir, 0700); err != nil {
		return nil, err
	}
	f, err := os.OpenFile(filepath.Join(c.DataDir, "supervisor.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	if err = lock(f); err != nil {
		f.Close()
		return nil, errors.New("supervisor data root already locked")
	}
	s, err := load(c.DataDir)
	if err != nil {
		f.Close()
		return nil, err
	}
	for i := range s.Jobs {
		if s.Jobs[i].Status == "running" {
			s.Jobs[i].Status = "needs_review"
		}
	}
	if err = save(c.DataDir, s); err != nil {
		f.Close()
		return nil, err
	}
	return &Engine{config: c, bridge: b, state: s, file: f, active: map[string]bool{}, pauseCheckAfter: map[string]time.Time{}}, nil
}
func (e *Engine) Close() error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.closed = true
	return e.file.Close()
}
func (e *Engine) Wait() { e.wg.Wait() }
func (e *Engine) Snapshot() State {
	e.mu.Lock()
	defer e.mu.Unlock()
	s := e.state
	s.Jobs = append([]Job(nil), s.Jobs...)
	s.Next = map[string]int64{}
	for k, v := range e.state.Next {
		s.Next[k] = v
	}
	return s
}
func (e *Engine) persist() error {
	if e.closed {
		return errors.New("supervisor closed")
	}
	data, err := json.Marshal(e.state)
	if err != nil {
		e.fatal = err
		return err
	}
	if bytes.Equal(data, e.persisted) {
		return nil
	}
	if err := save(e.config.DataDir, e.state); err != nil {
		e.fatal = err
		return err
	}
	e.persisted = data
	return nil
}
func (e *Engine) blocked(store string) bool {
	for _, j := range e.state.Jobs {
		if j.StoreID == store && (j.Status == "running" || j.Status == "needs_review") {
			return true
		}
	}
	return false
}
func (e *Engine) usedSlots() int {
	slots := map[string]bool{}
	for id := range e.active {
		slots[id] = true
	}
	for _, j := range e.state.Jobs {
		if j.Status == "running" || j.Status == "needs_review" {
			slots[j.ID] = true
		}
	}
	return len(slots)
}
func (e *Engine) prune() {
	for len(e.state.Jobs) >= 1000 {
		idx := -1
		for i, j := range e.state.Jobs {
			if j.Status == "complete" || j.Status == "paused" || j.Status == "failed" {
				idx = i
				break
			}
		}
		if idx < 0 {
			return
		}
		e.state.Jobs = append(e.state.Jobs[:idx], e.state.Jobs[idx+1:]...)
	}
}

// Tick coalesces overdue schedules into one occurrence and persists the claim
// before launching work. First configuration schedules one full interval ahead.
func (e *Engine) Tick(ctx context.Context, now time.Time) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.closed {
		return errors.New("supervisor closed")
	}
	if e.fatal != nil {
		return e.fatal
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	// Reconcile only correlated final receipts. A missing or live receipt never
	// releases a durable store block, even after the timeout/grace has elapsed.
	for i := range e.state.Jobs {
		j := &e.state.Jobs[i]
		if j.Status != "needs_review" {
			continue
		}
		r, err := e.bridge.Call(ctx, "receipt", j.StoreID, j.ID)
		if err == nil && r.JobID == j.ID && r.StoreID == j.StoreID && jobIdentifier.MatchString(r.ReceiptID) && (r.Status == "complete" || r.Status == "paused" || r.Status == "failed") {
			j.Status = r.Status
			j.ReceiptID = r.ReceiptID
			j.Finished = now.Unix()
		}
	}
	configured := map[string]bool{}
	for _, s := range e.config.Stores {
		configured[s.StoreID] = true
	}
	for k := range e.state.Next {
		if !configured[k] {
			delete(e.state.Next, k)
		}
	}
	for _, s := range e.config.Stores {
		next, ok := e.state.Next[s.StoreID]
		if !ok {
			e.state.Next[s.StoreID] = now.Unix() + s.IntervalSeconds
			continue
		}
		if now.Unix() >= next && !e.blocked(s.StoreID) {
			queued := false
			for _, j := range e.state.Jobs {
				if j.StoreID == s.StoreID && j.Status == "queued" {
					queued = true
				}
			}
			if !queued {
				e.prune()
				if len(e.state.Jobs) >= 1000 {
					return errors.New("state retention exhausted by unresolved jobs")
				}
				var id [16]byte
				if _, err := rand.Read(id[:]); err != nil {
					return err
				}
				e.state.Jobs = append(e.state.Jobs, Job{ID: hex.EncodeToString(id[:]), StoreID: s.StoreID, Period: next, Status: "queued"})
			}
			e.state.Next[s.StoreID] = now.Unix() + s.IntervalSeconds
		}
	}
	if err := e.persist(); err != nil {
		return err
	}
	for i := range e.state.Jobs {
		j := &e.state.Jobs[i]
		if !configured[j.StoreID] || j.Status != "queued" || e.blocked(j.StoreID) || e.usedSlots() >= e.config.MaxConcurrency {
			continue
		}
		// A paused queue polls at most once per 30 seconds. This cache only
		// delays dispatch; Python still checks its authoritative pause checkpoints.
		if now.Before(e.pauseCheckAfter[j.StoreID]) {
			continue
		}
		reply, err := e.bridge.Call(ctx, "status", j.StoreID, "")
		if err != nil {
			return errors.New("cannot confirm authoritative pause status")
		}
		if reply.Paused {
			e.pauseCheckAfter[j.StoreID] = now.Add(30 * time.Second)
			continue
		}
		delete(e.pauseCheckAfter, j.StoreID)
		j.Status = "running"
		j.Started = now.Unix()
		if err = e.persist(); err != nil {
			return err
		}
		job := *j
		e.active[job.ID] = true
		e.wg.Add(1)
		go e.execute(ctx, job)
	}
	return nil
}
func (e *Engine) update(id string, fn func(*Job)) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.closed {
		return
	}
	for i := range e.state.Jobs {
		if e.state.Jobs[i].ID == id {
			fn(&e.state.Jobs[i])
			break
		}
	}
	_ = e.persist()
}

type result struct {
	r           Reply
	err         error
	unconfirmed bool
}

func (e *Engine) execute(ctx context.Context, j Job) {
	defer e.wg.Done()
	done := make(chan result, 1)
	go func() {
		r, err := e.bridge.Call(context.Background(), "run", j.StoreID, j.ID)
		done <- result{r: r, err: err}
	}()
	timer := time.NewTimer(time.Duration(e.config.TimeoutSeconds) * time.Second)
	defer timer.Stop()
	var out result
	select {
	case out = <-done:
	case <-timer.C:
		out = e.cancelAndWait(j, done)
	case <-ctx.Done():
		out = e.cancelAndWait(j, done)
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.closed {
		return
	}
	// Unknown outcomes may still own a live child. Keep the global slot until
	// its Wait completes, in addition to the durable per-store block.
	if !out.unconfirmed {
		delete(e.active, j.ID)
	} else {
		go func() {
			r := <-done
			e.mu.Lock()
			defer e.mu.Unlock()
			if e.closed {
				return
			}
			delete(e.active, j.ID)
			for i := range e.state.Jobs {
				p := &e.state.Jobs[i]
				if p.ID == j.ID && r.err == nil && (r.r.Status == "complete" || r.r.Status == "paused" || r.r.Status == "failed") {
					p.Status = r.r.Status
					p.ReceiptID = r.r.ReceiptID
					p.Finished = time.Now().Unix()
				}
			}
			_ = e.persist()
		}()
	}
	for i := range e.state.Jobs {
		p := &e.state.Jobs[i]
		if p.ID != j.ID {
			continue
		}
		p.Finished = 0
		p.Status = "needs_review"
		if out.err == nil && (out.r.Status == "complete" || out.r.Status == "paused" || out.r.Status == "failed") {
			p.Status = out.r.Status
			p.Finished = time.Now().Unix()
			p.ReceiptID = out.r.ReceiptID
		}
		break
	}
	_ = e.persist()
}

// Cancellation is cooperative only. A non-responsive child remains alive and
// the durable needs_review record continues blocking this store.
func (e *Engine) cancelAndWait(j Job, done <-chan result) result {
	e.update(j.ID, func(p *Job) { p.CancelRequested = true })
	go func() { _, _ = e.bridge.Call(context.Background(), "cancel", j.StoreID, j.ID) }()
	timer := time.NewTimer(5 * time.Second)
	defer timer.Stop()
	select {
	case r := <-done:
		return r
	case <-timer.C:
		return result{err: errors.New("cooperative cancellation unconfirmed"), unconfirmed: true}
	}
}
