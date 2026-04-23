package main

// MARK: - Structs

type User struct {
	ID       int
	Name     string
	Email    string
	IsActive bool
}

type Point struct {
	X float64
	Y float64
}

type Rectangle struct {
	Origin Point
	Width  float64
	Height float64
}

// MARK: - Interfaces

type Reader interface {
	Read(p []byte) (n int, err error)
}

type Writer interface {
	Write(p []byte) (n int, err error)
}

type ReadWriter interface {
	Reader
	Writer
}

// MARK: - Functions

func Add(a int, b int) int {
	return a + b
}

func Greet(name string) string {
	return "Hello, " + name
}

func FetchUser(id int) *User {
	return nil
}

func ProcessItems(items []string, transform func(string) string) []string {
	result := make([]string, len(items))
	for i, item := range items {
		result[i] = transform(item)
	}
	return result
}

// MARK: - Methods

func (u *User) GetID() int {
	return u.ID
}

func (u *User) SetEmail(email string) {
	u.Email = email
}

func (p Point) Distance() float64 {
	return p.X + p.Y
}

// MARK: - Constants

const MaxUsers = 100

const StatusActive = "active"

const (
	StatusPending   = "pending"
	StatusInactive  = "inactive"
	StatusArchived  = "archived"
)

// MARK: - Variables

var GlobalCounter int

var DefaultUser *User
