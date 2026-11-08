package supervisor

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

type fakeBridge struct {
	paused      bool
	statusCalls int
}

func (f *fakeBridge) Call(_ context.Context, a, s, j string) (Reply, error) {
	if a == "status" {
		f.statusCalls++
		return Reply{Paused: f.paused}, nil
	}
	return Reply{JobID: j, StoreID: s, Status: "complete"}, nil
}
func testConfig(t *testing.T) Config {
	return Config{Python: filepath.Join(t.TempDir(), "python"), ServerDir: t.TempDir(), DataDir: t.TempDir(), MaxConcurrency: 2, TimeoutSeconds: 10, Stores: []Store{{StoreID: "demo", IntervalSeconds: 60}}}
}
func TestRecoveryBlocksUnknownStore(t *testing.T) {
	c := testConfig(t)
	s := State{Jobs: []Job{{ID: "12345678901234567890123456789012", StoreID: "demo", Status: "running", Period: 1, Started: 1}}, Next: map[string]int64{}}
	if err := save(c.DataDir, s); err != nil {
		t.Fatal(err)
	}
	e, err := Open(c, &fakeBridge{})
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if e.state.Jobs[0].Status != "needs_review" {
		t.Fatal(e.state)
	}
	if err = e.Tick(context.Background(), time.Now()); err != nil {
		t.Fatal(err)
	}
	if len(e.state.Jobs) != 1 {
		t.Fatal("unknown job repeated")
	}
}
func TestPauseAndCoalescing(t *testing.T) {
	c := testConfig(t)
	f := &fakeBridge{paused: true}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	now := time.Now()
	if err = e.Tick(context.Background(), now); err != nil {
		t.Fatal(err)
	}
	if len(e.state.Jobs) != 0 {
		t.Fatal("paused dispatch")
	}
	f.paused = false
	if err = e.Tick(context.Background(), now.Add(24*time.Hour)); err != nil {
		t.Fatal(err)
	}
	e.Wait()
	if len(e.Snapshot().Jobs) != 1 {
		t.Fatal("missed periods replayed")
	}
}
func TestRejectConfigAndCorruption(t *testing.T) {
	c := testConfig(t)
	c.Stores[0].StoreID = "../bad"
	if c.Validate() == nil {
		t.Fatal("unsafe store accepted")
	}
	c = testConfig(t)
	os.WriteFile(filepath.Join(c.DataDir, "state.json"), []byte("{} junk"), 0600)
	if e, err := Open(c, &fakeBridge{}); err == nil {
		e.Close()
		t.Fatal("corrupt state accepted")
	}
}
func TestExclusiveLock(t *testing.T) {
	c := testConfig(t)
	e, err := Open(c, &fakeBridge{})
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if other, err := Open(c, &fakeBridge{}); err == nil {
		other.Close()
		t.Fatal("duplicate supervisor accepted")
	}
}
func TestBoundedWriter(t *testing.T) {
	w := &boundedOutput{}
	p := make([]byte, 70000)
	n, err := w.Write(p)
	if n != len(p) || err != nil || len(w.data) != 65536 || !w.overflow {
		t.Fatal("output not bounded")
	}
}

type gatedBridge struct {
	mu      sync.Mutex
	running int
	maximum int
	stores  map[string]int
	overlap bool
	release chan struct{}
	cancel  chan string
}

func (f *gatedBridge) Call(_ context.Context, a, s, j string) (Reply, error) {
	if a == "status" {
		return Reply{}, nil
	}
	if a == "cancel" {
		f.cancel <- j
		return Reply{CancelRequested: true}, nil
	}
	if a == "receipt" {
		return Reply{Status: "unknown"}, nil
	}
	f.mu.Lock()
	f.running++
	f.stores[s]++
	if f.stores[s] > 1 {
		f.overlap = true
	}
	if f.running > f.maximum {
		f.maximum = f.running
	}
	f.mu.Unlock()
	<-f.release
	f.mu.Lock()
	f.running--
	f.stores[s]--
	f.mu.Unlock()
	return Reply{JobID: j, StoreID: s, Status: "complete"}, nil
}
func TestConcurrentStoresAndDurableClaim(t *testing.T) {
	c := testConfig(t)
	c.Stores = append(c.Stores, Store{StoreID: "second", IntervalSeconds: 60}, Store{StoreID: "third", IntervalSeconds: 60})
	f := &gatedBridge{stores: map[string]int{}, release: make(chan struct{}), cancel: make(chan string, 8)}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	now := time.Now()
	if err = e.Tick(context.Background(), now); err != nil {
		t.Fatal(err)
	}
	if err = e.Tick(context.Background(), now.Add(time.Minute)); err != nil {
		t.Fatal(err)
	}
	disk, err := load(c.DataDir)
	if err != nil {
		t.Fatal(err)
	}
	running := 0
	for _, j := range disk.Jobs {
		if j.Status == "running" {
			running++
		}
	}
	if running != 2 {
		t.Fatal("claims not persisted before execution", disk)
	}
	if err = e.Tick(context.Background(), now.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	close(f.release)
	e.Wait()
	if err = e.Tick(context.Background(), now.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	e.Wait()
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.maximum > 2 || f.overlap {
		t.Fatal("concurrency exceeded", f.maximum, f.overlap)
	}
}
func TestTimeoutCooperativeCancellation(t *testing.T) {
	c := testConfig(t)
	c.TimeoutSeconds = 1
	f := &gatedBridge{stores: map[string]int{}, release: make(chan struct{}), cancel: make(chan string, 8)}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	now := time.Now()
	_ = e.Tick(context.Background(), now)
	_ = e.Tick(context.Background(), now.Add(time.Minute))
	select {
	case <-f.cancel:
	case <-time.After(3 * time.Second):
		t.Fatal("no cooperative cancellation")
	}
	s := e.Snapshot()
	if !s.Jobs[0].CancelRequested || s.Jobs[0].Status != "running" {
		t.Fatal("claimed stopped before receipt", s)
	}
	close(f.release)
	e.Wait()
	if e.Snapshot().Jobs[0].Status != "complete" {
		t.Fatal("final response ignored")
	}
}
func TestStateBoundsAndNoTrailingJSON(t *testing.T) {
	c := testConfig(t)
	s := State{Version: 1, Next: map[string]int64{}, Jobs: []Job{{ID: "bad", StoreID: "demo", Status: "complete"}}}
	if err := save(c.DataDir, s); err != nil {
		t.Fatal(err)
	}
	if _, err := load(c.DataDir); err == nil {
		t.Fatal("malformed identity accepted")
	}
	if decode([]byte(`{} {}`), &s) == nil {
		t.Fatal("extra JSON accepted")
	}
}

type recoveredBridge struct{ fakeBridge }

func (f recoveredBridge) Call(ctx context.Context, a, s, j string) (Reply, error) {
	if a == "receipt" {
		return Reply{JobID: j, StoreID: s, Status: "complete", ReceiptID: "11111111111111111111111111111111"}, nil
	}
	return f.fakeBridge.Call(ctx, a, s, j)
}
func TestFinalReceiptReconcilesInterruptedRun(t *testing.T) {
	c := testConfig(t)
	s := State{Version: 1, Next: map[string]int64{}, Jobs: []Job{{ID: "12345678901234567890123456789012", StoreID: "demo", Status: "running", Period: 1, Started: 1}}}
	if err := save(c.DataDir, s); err != nil {
		t.Fatal(err)
	}
	e, err := Open(c, recoveredBridge{})
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if err = e.Tick(context.Background(), time.Now()); err != nil {
		t.Fatal(err)
	}
	if e.Snapshot().Jobs[0].Status != "complete" {
		t.Fatal("final receipt did not reconcile")
	}
}

func TestMain(m *testing.M) {
	if os.Getenv("SUPERVISOR_TEST_CHILD") == "1" {
		if os.Getenv("SUPERVISOR_TEST_SLEEP") == "1" {
			time.Sleep(time.Minute)
		}
		fmt.Print(os.Getenv("SUPERVISOR_TEST_REPLY"))
		os.Exit(0)
	}
	os.Exit(m.Run())
}
func TestFixedBridgeRejectsMalformedAndUnboundedReplies(t *testing.T) {
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	c := testConfig(t)
	c.Python = exe
	b := PythonBridge{Config: c}
	t.Setenv("SUPERVISOR_TEST_CHILD", "1")
	for _, body := range []string{`{}`, `{"paused":false}`, `{"paused":false,"state":"enabled"} {}`, strings.Repeat("x", 70000)} {
		t.Setenv("SUPERVISOR_TEST_REPLY", body)
		if _, err = b.Call(context.Background(), "status", "demo", ""); err == nil {
			t.Fatal("accepted malformed response")
		}
	}
	t.Setenv("SUPERVISOR_TEST_REPLY", `{"paused":true,"state":"paused"}`)
	r, err := b.Call(context.Background(), "status", "demo", "")
	if err != nil || !r.Paused {
		t.Fatal("valid status rejected", err)
	}
	if _, err = b.Call(context.Background(), "run;touch evil", "demo", ""); err == nil {
		t.Fatal("arbitrary action accepted")
	}
	if _, err = b.Call(context.Background(), "status", "../evil", ""); err == nil {
		t.Fatal("arbitrary store accepted")
	}
	t.Setenv("SUPERVISOR_TEST_REPLY", `{"job_id":"12345678901234567890123456789012","store_id":"other","status":"complete","receipt_id":"11111111111111111111111111111111"}`)
	if _, err = b.Call(context.Background(), "run", "demo", "12345678901234567890123456789012"); err == nil {
		t.Fatal("identity mismatch accepted")
	}
}
func TestUnconfirmedTimeoutRetainsSlotAndStoreBlock(t *testing.T) {
	c := testConfig(t)
	c.TimeoutSeconds = 1
	c.MaxConcurrency = 1
	c.Stores = append(c.Stores, Store{StoreID: "second", IntervalSeconds: 60})
	f := &gatedBridge{stores: map[string]int{}, release: make(chan struct{}), cancel: make(chan string, 8)}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	now := time.Now()
	_ = e.Tick(context.Background(), now)
	_ = e.Tick(context.Background(), now.Add(time.Minute))
	e.Wait()
	s := e.Snapshot()
	if s.Jobs[0].Status != "needs_review" {
		t.Fatal("unknown timeout claimed final", s)
	}
	if err = e.Tick(context.Background(), now.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	if e.Snapshot().Jobs[1].Status != "queued" {
		t.Fatal("live unknown process released concurrency slot")
	}
	close(f.release)
}

func TestHungReadHelperHasDeadline(t *testing.T) {
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	c := testConfig(t)
	c.Python = exe
	t.Setenv("SUPERVISOR_TEST_CHILD", "1")
	t.Setenv("SUPERVISOR_TEST_SLEEP", "1")
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	start := time.Now()
	if _, err = (PythonBridge{Config: c}).Call(ctx, "status", "demo", ""); err == nil {
		t.Fatal("hung helper accepted")
	}
	if time.Since(start) > 2*time.Second {
		t.Fatal("helper ignored deadline")
	}
}
func TestUnknownStartupConsumesGlobalCapacity(t *testing.T) {
	c := testConfig(t)
	c.MaxConcurrency = 1
	c.Stores = append(c.Stores, Store{StoreID: "second", IntervalSeconds: 60})
	s := State{Version: 1, Next: map[string]int64{"second": 1}, Jobs: []Job{{ID: "12345678901234567890123456789012", StoreID: "demo", Status: "running", Period: 1, Started: 1}}}
	_ = save(c.DataDir, s)
	e, err := Open(c, &fakeBridge{})
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if err = e.Tick(context.Background(), time.Now()); err != nil {
		t.Fatal(err)
	}
	if e.Snapshot().Jobs[1].Status != "queued" {
		t.Fatal("unknown orphan did not consume global capacity")
	}
}
func TestLateResultCannotWriteAfterLockReleased(t *testing.T) {
	c := testConfig(t)
	f := &gatedBridge{stores: map[string]int{}, release: make(chan struct{}), cancel: make(chan string, 8)}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	_ = e.Tick(context.Background(), now)
	_ = e.Tick(context.Background(), now.Add(time.Minute))
	if err = e.Close(); err != nil {
		t.Fatal(err)
	}
	next, err := Open(c, &fakeBridge{})
	if err != nil {
		t.Fatal(err)
	}
	defer next.Close()
	close(f.release)
	e.Wait()
	disk, err := load(c.DataDir)
	if err != nil {
		t.Fatal(err)
	}
	if disk.Jobs[0].Status != "needs_review" {
		t.Fatal("closed supervisor overwrote new owner")
	}
}

func TestStateRequiresExplicitTopLevelFields(t *testing.T) {
	for _, body := range []string{`{}`, `null`, `{"version":1}`, `{"version":1,"next":{},"jobs":null}`, `{"version":1,"next":null,"jobs":[]}`, `{"next":{},"jobs":[]}`} {
		t.Run(body, func(t *testing.T) {
			c := testConfig(t)
			if err := os.WriteFile(filepath.Join(c.DataDir, "state.json"), []byte(body), 0600); err != nil {
				t.Fatal(err)
			}
			if e, err := Open(c, &fakeBridge{}); err == nil {
				e.Close()
				t.Fatal("accepted incomplete durable state")
			}
		})
	}
}

func TestPausedQueuePollBackoff(t *testing.T) {
	c := testConfig(t)
	f := &fakeBridge{paused: true}
	e, err := Open(c, f)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	now := time.Now().Truncate(time.Second)
	if err = e.Tick(context.Background(), now); err != nil {
		t.Fatal(err)
	}
	due := now.Add(time.Minute)
	for second := 0; second < 30; second++ {
		if err = e.Tick(context.Background(), due.Add(time.Duration(second)*time.Second)); err != nil {
			t.Fatal(err)
		}
	}
	if f.statusCalls != 1 {
		t.Fatalf("paused queue spawned %d status helpers before backoff", f.statusCalls)
	}
	f.paused = false
	if err = e.Tick(context.Background(), due.Add(30*time.Second)); err != nil {
		t.Fatal(err)
	}
	e.Wait()
	s := e.Snapshot()
	if f.statusCalls != 2 || len(s.Jobs) != 1 || s.Jobs[0].Status != "complete" {
		t.Fatal("resumed queue did not dispatch once", f.statusCalls, s)
	}
	if s.Next["demo"] != due.Add(time.Minute).Unix() {
		t.Fatal("pause polling changed persisted schedule")
	}
}
