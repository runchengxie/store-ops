//go:build linux || darwin || freebsd

package supervisor

import (
	"os"
	"path/filepath"
	"syscall"
)

func lock(f *os.File) error { return syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB) }
func replace(from, to string) error {
	if err := os.Rename(from, to); err != nil {
		return err
	}
	d, err := os.OpenFile(filepath.Dir(to), os.O_RDONLY, 0)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}
