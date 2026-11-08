package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"store-ops/supervisor/internal/supervisor"
	"syscall"
	"time"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	if len(os.Args) < 2 || (os.Args[1] != "run" && os.Args[1] != "status") {
		return fmt.Errorf("usage: store-ops-supervisor run|status --config PATH")
	}
	f := flag.NewFlagSet(os.Args[1], flag.ContinueOnError)
	path := f.String("config", "", "configuration JSON")
	if err := f.Parse(os.Args[2:]); err != nil {
		return err
	}
	if *path == "" || f.NArg() != 0 {
		return fmt.Errorf("a configuration file is required")
	}
	c, err := supervisor.LoadConfig(*path)
	if err != nil {
		return err
	}
	if os.Args[1] == "status" {
		return supervisor.PrintStatus(c, os.Stdout)
	}
	e, err := supervisor.Open(c, supervisor.PythonBridge{Config: c})
	if err != nil {
		return err
	}
	defer e.Close()
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		if err = e.Tick(ctx, time.Now()); err != nil && ctx.Err() == nil {
			return err
		}
		select {
		case <-ctx.Done():
			e.Wait()
			return nil
		case <-ticker.C:
		}
	}
}
