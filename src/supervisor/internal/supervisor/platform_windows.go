package supervisor

import (
	"os"
	"syscall"
	"unsafe"
)

var kernel = syscall.NewLazyDLL("kernel32.dll")
var lockFileEx = kernel.NewProc("LockFileEx")
var moveFileEx = kernel.NewProc("MoveFileExW")

func lock(f *os.File) error {
	var ov syscall.Overlapped
	r, _, e := lockFileEx.Call(f.Fd(), 3, 0, 1, 0, uintptr(unsafe.Pointer(&ov)))
	if r == 0 {
		return e
	}
	return nil
}
func replace(from, to string) error {
	a, e := syscall.UTF16PtrFromString(from)
	if e != nil {
		return e
	}
	b, e := syscall.UTF16PtrFromString(to)
	if e != nil {
		return e
	}
	r, _, e := moveFileEx.Call(uintptr(unsafe.Pointer(a)), uintptr(unsafe.Pointer(b)), 0x1|0x8)
	if r == 0 {
		return e
	}
	return nil
}
