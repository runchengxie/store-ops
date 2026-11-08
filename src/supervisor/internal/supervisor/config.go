package supervisor

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
)

var identifier = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$`)
var jobIdentifier = regexp.MustCompile(`^[a-f0-9]{32}$`)

type Store struct {
	StoreID         string `json:"store_id"`
	IntervalSeconds int64  `json:"interval_seconds"`
}
type Config struct {
	Python         string  `json:"python"`
	ServerDir      string  `json:"server_dir"`
	DataDir        string  `json:"data_dir"`
	Stores         []Store `json:"stores"`
	MaxConcurrency int     `json:"max_concurrency"`
	TimeoutSeconds int64   `json:"timeout_seconds"`
}

func (c Config) Validate() error {
	if !filepath.IsAbs(c.Python) || !filepath.IsAbs(c.ServerDir) || !filepath.IsAbs(c.DataDir) {
		return errors.New("paths must be absolute")
	}
	if c.MaxConcurrency < 1 || c.MaxConcurrency > 8 || c.TimeoutSeconds < 1 || c.TimeoutSeconds > 86400 || len(c.Stores) < 1 || len(c.Stores) > 100 {
		return errors.New("configuration bounds exceeded")
	}
	seen := map[string]bool{}
	for _, s := range c.Stores {
		if !identifier.MatchString(s.StoreID) || seen[s.StoreID] || s.IntervalSeconds < 1 || s.IntervalSeconds > 31536000 {
			return errors.New("invalid or duplicate store")
		}
		seen[s.StoreID] = true
	}
	return nil
}
func decode(data []byte, v any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(v); err != nil {
		return err
	}
	if d.Decode(new(any)) != io.EOF {
		return errors.New("trailing JSON")
	}
	return nil
}
func LoadConfig(path string) (Config, error) {
	c := Config{MaxConcurrency: 2, TimeoutSeconds: 3600}
	data, err := readBounded(path, 65536)
	if err == nil {
		err = decode(data, &c)
	}
	if err == nil {
		err = c.Validate()
	}
	return c, err
}
func readBounded(path string, limit int64) ([]byte, error) {
	f, e := os.Open(path)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, limit+1))
	if len(b) > int(limit) {
		return nil, errors.New("file exceeds limit")
	}
	return b, e
}
