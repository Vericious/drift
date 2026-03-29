# Sample TypeScript Documentation

## User Interface

| Property | Type   | Description           |
|----------|--------|-----------------------|
| id       | number | The user's unique ID  |
| name     | string | The user's name       |
| email    | string | The user's email      |

## Options Interface

```typescript
interface Options {
  timeout: number;
  retries: number;
  debug: boolean;
}
```

## Status Enum

| Member   | Value     |
|----------|-----------|
| ACTIVE   | "active"  |
| INACTIVE | "inactive"|
