module github.com/example/myproject

go 1.21

require (
	github.com/pkg/errors v0.9.1
	golang.org/x/net v0.17.0
)

require (
	golang.org/x/text v0.13.0 // indirect
)

replace github.com/pkg/errors => ../errors

exclude github.com/bad/pkg v0.0.0