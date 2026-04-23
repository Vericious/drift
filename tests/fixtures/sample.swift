// Swift sample declarations for testing the SwiftExtractor

import Foundation

// MARK: - Structs

public struct User {
    let id: Int
    var name: String
    var email: String?
    var isActive: Bool

    func greet() -> String {
        return "Hello, \(name)!"
    }

    func toDict() -> [String: Any] {
        return ["id": id, "name": name]
    }
}

struct Point {
    var x: Double
    var y: Double
}

struct Rectangle {
    var origin: Point
    var width: Double
    var height: Double

    var area: Double {
        return width * height
    }

    func contains(_ point: Point) -> Bool {
        return point.x >= origin.x && point.x <= origin.x + width &&
               point.y >= origin.y && point.y <= origin.y + height
    }
}

// MARK: - Classes

class ViewController {
    var title: String?
    var items: [String]

    init() {
        items = []
    }

    func addItem(_ item: String) {
        items.append(item)
    }

    func removeItem(at index: Int) {
        items.remove(at: index)
    }
}

open class Animal {
    var name: String

    init(name: String) {
        self.name = name
    }

    func speak() -> String {
        return ""
    }
}

class Dog: Animal {
    var breed: String

    init(name: String, breed: String) {
        self.breed = breed
        super.init(name: name)
    }

    override func speak() -> String {
        return "Woof!"
    }
}

// MARK: - Enums

enum Direction {
    case north
    case south
    case east
    case west
}

enum Status {
    case pending
    case active
    case suspended
}

enum Color: String {
    case red = "red"
    case green = "green"
    case blue = "blue"
}

enum Priority: Int {
    case low = 1
    case medium = 2
    case high = 3
}

// MARK: - Protocols

protocol Drawable {
    func draw()
    var strokeWidth: Double { get set }
}

protocol Identifiable {
    var id: String { get }
}

protocol Configurable {
    var debug: Bool { get set }
    var apiUrl: String { get }
    func configure()
}

// MARK: - Protocol with associated types

protocol Container {
    associatedtype Item
    var count: Int { get }
    mutating func add(_ item: Item)
    func get(at index: Int) -> Item?
}

// MARK: - Standalone Functions

func add(_ a: Int, _ b: Int) -> Int {
    return a + b
}

func fetchUser(id: Int, completion: (User?) -> Void) {
    completion(nil)
}

func processItems(_ items: [String], transform: (String) -> String) -> [String] {
    return items.map(transform)
}

// MARK: - Extensions

extension User {
    func fullName() -> String {
        return "\(name) (ID: \(id))"
    }

    var displayName: String {
        return name
    }
}

extension ViewController {
    func clearItems() {
        items.removeAll()
    }

    var itemCount: Int {
        return items.count
    }
}

// MARK: - Nested Types

struct Container {
    struct Inner {
        var value: Int
    }

    var inner: Inner

    mutating func update(_ newValue: Int) {
        inner.value = newValue
    }
}
