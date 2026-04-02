// TypeScript interface, type, and enum samples

// Basic interface
export interface User {
  id: number;
  name: string;
  email?: string;
  isActive: boolean;
}

// Interface with extends
interface AdminUser extends User {
  role: string;
  permissions: string[];
}

// Nested interface
interface Address {
  street: string;
  city: string;
  zipCode: string;
  country?: string;
}

interface Company {
  name: string;
  address: Address;
  employees: number;
}

// Type alias — object type
type UserProfile = {
  username: string;
  avatar: string;
  bio: string;
  createdAt: Date;
};

// Type alias — union type
type Status = "pending" | "active" | "suspended";

// Type alias — primitive
type UserId = string;
type Timestamp = number;

// String enum
export enum Color {
  Red = "red",
  Green = "green",
  Blue = "blue",
}

// Numeric enum
enum Direction {
  Up,
  Down,
  Left,
  Right,
}

// Const enum
const enum Priority {
  Low = 1,
  Medium = 2,
  High = 3,
}

// Interface with method signatures
interface Config {
  debug: boolean;
  apiUrl: string;
  timeout: number;
  getValue(key: string): any;
  setValue(key: string, value: any): void;
}

// Single-line interface
interface SingleLine { id: number; name: string; }

// Interface with readonly properties
interface ReadonlyUser {
  readonly id: number;
  readonly name: string;
  email?: string;
}

// Readonly and optional combined
interface ReadonlyOptional {
  readonly id?: number;
  readonly name?: string;
}

// Nested type annotation
interface NestedType {
  handler: (event: Event) => void;
  callback: (data: string, error: Error | null) => Promise<void>;
}
