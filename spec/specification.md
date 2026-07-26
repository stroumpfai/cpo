# CPO Web Application - Specification

## 1. Overview

The CPO (Chief Pizza Officer) web application is a team pizza ordering system designed to streamline lunch order collection. The application supports administrators managing CPO accounts, CPOs managing team ordering sessions, and team members placing orders without authentication.

### Key Objectives
- Simplify pizza order collection for teams
- Provide real-time order summaries
- Support multiple independent teams
- Run as a single containerized application

---

## 2. Roles & Access Control

### 2.1 Administrator
- **Access**: Web-based login with password
- **Credentials**: Stored as hashed password in JSON configuration file
- **Permissions**:
  - Create new CPO accounts (name, email, initial password)
  - View list of all CPOs
  - Manage CPO credentials (password reset)

### 2.2 Chief Pizza Officer (CPO)
- **Access**: Web-based login with credentials
- **Credentials**: Username/email + hashed password stored in JSON configuration file
- **Session Duration**: JWT tokens valid for 1 month (30 days)
- **Permissions**:
  - Manage one team
  - Open/close ordering sessions
  - Edit pizza menu (add/remove pizzas with name and price)
  - View real-time order summary
  - Print order summary
  - Generate unique team ordering link

### 2.3 Team Member (End-User)
- **Access**: Unique link provided by CPO (no login required)
- **Link Format**: Random alphanumeric, unique per team (e.g., `orders.app/x7k9mP2qRvL5j`)
- **Permissions**:
  - Submit orders when session is active
  - Modify existing orders (before session closes)
  - Cancel orders (before session closes)
  - View session status (active/closed)

---

## 3. Session Management

### 3.1 Session Lifecycle
- **Creation**: CPO sets session date, start time, and end time
- **Activation**: Session automatically opens at the specified start time
- **Active State**: Team members can place/modify/cancel orders
- **Grace Period**: 2-minute grace period after end time for final orders
  - Orders submitted within 2 minutes after end time are accepted
  - Orders submitted more than 2 minutes after end time are rejected
- **Closure**: Session automatically closes after grace period expires
- **Uniqueness**: Only one active session per team at any given time
- **Multiple Teams**: Multiple teams can have simultaneous sessions

### 3.2 Session Status Indicators
**Active Session**:
- Team members see ordering form
- Display countdown timer to session end
- Accept new orders, modifications, and cancellations

**Closed Session**:
- Team members see "Session is closed" message
- Display when the next session opens (if scheduled)
- No new orders accepted (even if within grace period)

---

## 4. Order Management

### 4.1 Order Placement (Add-to-Order Pattern)
**Form Fields**:
- Team member name (text input, required)
- Pizza type (dropdown selection from CPO's menu, required)
- "Add to Order" button

**Workflow**:
1. Team member enters their name
2. Selects a pizza type
3. Clicks "Add to Order"
4. Pizza is added to visible order list below the form
5. Team member can repeat steps 2-3 to add more pizzas (same or different types)
6. Once all pizzas selected, click "Submit Order" to send all items

**Validation**:
- Member name must not be empty
- Pizza type must be selected
- Rate limiting: Maximum 1 order submission per IP address per 5 seconds
- If rate limit exceeded: Display message "Too many orders. Please wait 5 seconds before trying again"

**Result of Submission**:
- Creates one order record per pizza selected
- Example: If "Alice" adds Margherita + Pepperoni + Hawaiian, creates 3 orders:
  - Alice | Margherita | 1 pizza
  - Alice | Pepperoni | 1 pizza
  - Alice | Hawaiian | 1 pizza

### 4.2 Order Cancellation (CPO-Only)
- **End-users**: Cannot modify or cancel orders after submission
- **CPO**: Can delete individual orders from summary dashboard
- **Display to End-users**: "Orders cannot be modified. Contact CPO if needed."

### 4.3 Protection Against Abuse
- **Rate Limiting**: Prevents spam ordering (1 submission per IP per 5 seconds)
- **CPO Oversight**: Member names and IPs visible in summary for review and manual deletion of suspicious orders

---

## 5. Pizza Menu Management

### 5.1 Menu Structure
**Per CPO**:
- Each CPO maintains their own pizza menu
- Menu persists across sessions

**Pizza Item Fields**:
- Name (string, required, unique per menu)
- Price (decimal, required, minimum 0.01)

### 5.2 Menu Operations
- **Add Pizza**: CPO enters name and price, creates new menu item
- **Edit Pizza**: CPO can update name and/or price
- **Remove Pizza**: CPO can delete pizza from menu
- **Validation**: Prevent duplicate pizza names within same menu

---

## 6. Order Summary

### 6.1 Summary Views
**CPO Dashboard** displays two views (selectable tabs):

**View 1: Distribution Summary (Per Member & Pizza)**
- Columns: Member Name | Client IP | Pizza Type | Price | Delete Action
- Sorted by member name
- Shows each order item (one pizza per row)
- **CPO Oversight**: Member names AND client IPs visible for review of:
  - Suspicious patterns or multiple orders from same IP
  - Multiple orders from unusual IPs
  - Unusual member names
- **CPO Actions**: Can delete individual orders directly from this view

**View 2: Pizzeria Summary (Consolidated)**
- Columns: Pizza Type | Count | Total Price
- Sorted by pizza type
- Aggregates order counts for ordering from pizzeria
- Shows totals only (member names and IPs hidden in consolidated view)

### 6.2 Summary Updates
- **Trigger**: Each new order submission, modification, or cancellation
- **Refresh**: Manual refresh button (SSE real-time updates sent to connected clients)
- **Persistence**: Summary data stored for duration of session

### 6.3 Summary Lifecycle
- **Session Start**: New session begins with empty summary
- **During Session**: Summary accumulates orders
- **Session Close**: Final summary locked and available for export
- **New Session**: Previous summary cleared, new session starts fresh
- **Archival**: Previous session data cleared from active display

### 6.4 Summary Export
- **Format**: Plain text table (tab-separated values)
- **Delivery**: Downloadable text file or browser print dialog
- **Content**: Both Distribution and Pizzeria views available for export

---

## 7. Data Models

### 7.1 Administrator
```json
{
  "username": "admin",
  "password_hash": "<bcrypt_hash>",
  "created_at": "2026-05-14T10:00:00Z"
}
```

### 7.2 CPO Account
```json
{
  "id": "<uuid>",
  "username": "john_doe",
  "email": "john@company.com",
  "password_hash": "<bcrypt_hash>",
  "team_name": "Engineering Team",
  "created_at": "2026-05-14T10:00:00Z",
  "currency": "CHF",
  "member_identifier": "name"
}
```
**Notes**: `member_identifier` is `"name"` (default) or `"email"` and decides what the public
ordering form asks team members for. CPOs who announce a delivery by email need addresses; those
who announce it verbally do not.

### 7.3 Pizza Menu
```json
{
  "cpo_id": "<uuid>",
  "pizzas": [
    {
      "id": "<uuid>",
      "name": "Margherita",
      "price": 12.50
    }
  ]
}
```

### 7.4 Session
```json
{
  "id": "<uuid>",
  "cpo_id": "<uuid>",
  "team_name": "Engineering Team",
  "unique_link": "x7k9mP2qRvL5j",
  "session_date": "2026-05-14",
  "start_time": "11:30",
  "end_time": "12:00",
  "created_at": "2026-05-14T10:00:00Z",
  "status": "active|closed"
}
```
**Notes**: `unique_link` is a random alphanumeric string (16+ characters) generated to prevent unauthorized access to other teams' sessions.

### 7.5 Order
```json
{
  "id": "<uuid>",
  "session_id": "<uuid>",
  "member_name": "Alice",
  "pizza_id": "<uuid>",
  "pizza_name": "Margherita",
  "pizza_price": 12.50,
  "quantity": 1,
  "total_price": 12.50,
  "created_at": "2026-05-14T11:35:00Z",
  "client_ip": "192.168.1.100"
}
```
**Notes**: Each order represents one pizza for one member. If a member wants multiple pizzas, multiple orders are created in a single submission.

`member_name` carries whichever identity the owning CPO's `member_identifier` asks for — a display
name or an email address. The value is stripped in both modes; in email mode it is additionally
validated (RFC 5322 syntax, no DNS deliverability check) and lower-cased, so the dashboard's
distinct-member count treats `Alice@x` and `alice@x` as one person. Lower-casing the local part
deviates from RFC 5321, which declares it case-sensitive; every mail provider in practice does the
same. Orders are never rewritten when the setting changes, so a session whose mode was flipped
mid-flight holds whatever each member submitted at the time.

---

## 8. Security & Protection Measures

### 8.0 Personal Data
When a CPO sets `member_identifier` to `"email"`, the order summary stores and displays team
members' email addresses alongside their client IPs. This raises the sensitivity of the summary and
SSE endpoints, which remain CPO-authenticated and scoped to the requesting CPO's own sessions. The
public ordering page also remembers the member's address in browser `localStorage`, keyed by team
link, and offers a "not you? clear" control for shared or kiosk machines.

### 8.1 Rate Limiting
**Mechanism**: Prevent spam and abuse by limiting order submissions from the same IP address.

**Rules**:
- Maximum 1 order submission per IP address per 5 seconds
- Client IP is captured with each order
- Subsequent requests within 5-second window return HTTP 429 (Too Many Requests)

**User Feedback**:
- Display message: "Too many orders. Please wait 5 seconds before trying again."
- Countdown timer showing seconds remaining (optional)

**Rationale for 5 Seconds**:
- Accounts for multiple team members sharing the same external office IP
- Prevents rapid-fire spam while allowing reasonable user flow
- 5-second window is long enough to catch intentional spam, short enough to not frustrate legitimate users

**Benefits**:
- Prevents rapid-fire spam from single location
- Prevents automated/bot attacks
- Simple to implement
- Works in office environments with shared IP

### 8.2 CPO Oversight with IP Tracking
**Mechanism**: CPO can review all orders by member name AND client IP address in the summary view.

**Features**:
- Summary shows member name, pizza type, and client IP for each order
- CPO can identify suspicious patterns:
  - Same IP address placing many orders rapidly (even if respecting rate limit)
  - Orders from unfamiliar names
  - Unusual IP addresses not typical for the team's office network
- CPO can delete individual orders before or after session closes
- Deleted orders are logged (timestamp, CPO action)

**IP Tracking Benefits**:
- Identifies coordinated spam (multiple orders from same IP)
- Complements rate limiting (rate limit prevents rapid submissions, IP tracking shows patterns)
- Helps CPO distinguish legitimate office users from trolls
- Auditable history of which IPs placed orders

**Actions Available**:
- View all orders by member name and IP
- Filter/sort by client IP to identify patterns
- Delete individual orders with reason/notes
- Review order totals and summaries

### 8.3 Combined Protection Strategy
These mechanisms work together:
1. **Rate limit** blocks rapid spam (1 submission per IP per 5 seconds)
2. **CPO oversight** catches patterns and malicious orders via IP tracking
3. **Random session link** prevents unauthorized access to other teams' sessions

A bad actor would need to:
- Know the session link (requires being informed by team/CPO)
- Work around rate limiting (limited to 1 submission per IP per 5 seconds)
- Avoid CPO's review and IP tracking (CPO can see IP and delete suspicious orders)

---

## 9. Technical Architecture

### 8.1 Frontend
- **Framework**: React
- **Deployment**: Single HTML/JS bundle served from backend
- **Responsiveness**: Mobile-first design, works on phones, tablets, desktops
- **Real-time Updates**: Server-Sent Events (SSE) for live summary updates

### 8.2 Backend
- **Framework**: FastAPI (Python 3.14)
- **Server**: uvicorn
- **API Style**: RESTful with SSE endpoint for real-time updates
- **Authentication**: JWT tokens (1 month expiry)

### 8.3 Storage
- **Admin & CPO Credentials**: JSON file (mounted as volume)
  - Path: `/app/config/config.json`
  - Passwords hashed with bcrypt
- **Sessions & Orders**: JSON-based file storage (mounted as volume)
  - Path: `/app/data/`
  - One directory per CPO
  - Session files stored by session ID
- **Pizza Menus**: JSON file storage per CPO
  - Persists across sessions

### 8.4 Containerization
- **Base Image**: `python:3.14-slim` or `python:3.14-alpine` (minimal size)
- **Single Container**: Application runs as single service
- **Volumes**:
  - `/app/config/` - Configuration file (admin password, CPO credentials)
  - `/app/data/` - Session and order data
- **Port**: 8000 (FastAPI default)

---

## 9. API Specification

### 9.1 Authentication Endpoints

**POST /api/auth/login**
- **Request**: `{ "username": "string", "password": "string" }`
- **Response**: `{ "token": "jwt_token", "expires_in": 2592000 }`
- **Roles**: Admin, CPO

**POST /api/auth/logout**
- **Request**: (no body, requires JWT)
- **Response**: `{ "message": "Logged out" }`

### 9.2 Rate Limiting Headers
Order submission endpoint includes rate limiting:
- **Response Headers**: `X-RateLimit-Limit: 1`, `X-RateLimit-Remaining: 0`, `X-RateLimit-Reset: <timestamp>`
- **On Limit Exceeded**: HTTP 429 (Too Many Requests)
- **Response**: `{ "error": "Too many requests. Please wait 5 seconds before trying again.", "retry_after": 5 }`

### 9.3 Admin Endpoints

**POST /api/admin/cpos**
- **Request**: `{ "username": "string", "email": "string", "team_name": "string", "initial_password": "string" }`
- **Response**: `{ "id": "uuid", "username": "string", ... }`

**GET /api/admin/cpos**
- **Response**: `[{ "id": "uuid", "username": "string", "team_name": "string", ... }]`

### 9.3 CPO Endpoints

**GET /api/cpo/me**
- **Response**: Current CPO's profile and team info, including `currency` and `member_identifier`

**PATCH /api/cpo/member-identifier**
- **Request**: `{ "member_identifier": "name" | "email" }`
- **Response**: The updated CPO profile
- **Errors**: any other value → HTTP 422
- **Notes**: Read live on every public request rather than snapshotted onto a session, so the
  change takes effect immediately. Orders already submitted keep the value they were entered with.

**POST /api/cpo/sessions**
- **Request**: `{ "session_date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM" }`
- **Response**: `{ "id": "uuid", "unique_link": "string", "session_date": "...", "start_time": "...", "end_time": "..." }`

**GET /api/cpo/sessions**
- **Response**: List of all sessions for current CPO

**GET /api/cpo/sessions/{session_id}/summary**
- **Response**: `{ "distribution": [...], "pizzeria": [...] }`

**GET /api/cpo/sessions/{session_id}/summary/sse**
- **Stream**: Server-Sent Events with summary updates

**POST /api/cpo/menu**
- **Request**: `{ "name": "string", "price": 12.50 }`
- **Response**: `{ "id": "uuid", "name": "string", "price": 12.50 }`

**GET /api/cpo/menu**
- **Response**: `[{ "id": "uuid", "name": "string", "price": 12.50 }]`

**PUT /api/cpo/menu/{pizza_id}**
- **Request**: `{ "name": "string", "price": 12.50 }`
- **Response**: Updated pizza item

**DELETE /api/cpo/menu/{pizza_id}**
- **Response**: `{ "message": "Pizza removed" }`

### 9.4 Team Member Endpoints (No Authentication)

**GET /api/orders/{unique_link}**
- **Response**: 
```json
{
  "session_id": "uuid",
  "status": "active|closed",
  "pizzas": [
    { "id": "uuid", "name": "Margherita", "price": 12.50 },
    { "id": "uuid", "name": "Pepperoni", "price": 13.50 }
  ],
  "message": "string|null",
  "currency": "CHF",
  "member_identifier": "name"
}
```
- **Notes**: `message` field contains session status (e.g., "Session is closed").
  `member_identifier` tells the client whether to ask for a name or an email.

**POST /api/orders/{unique_link}/submit**
- **Request**:
```json
{
  "items": [
    { "member_name": "string", "pizza_id": "uuid", "comment": "string|null" }
  ]
}
```
- **Response**: 
```json
{
  "status": "submitted",
  "orders_created": 3,
  "order_ids": ["uuid1", "uuid2", "uuid3"]
}
```
- **Errors**: 
  - `{ "detail": "Session is closed" }` (HTTP 403)
  - `{ "detail": "Name is required." }` / `{ "detail": "Email address is required." }` (HTTP 400 — the value was empty after stripping)
  - `{ "detail": "Name must be 100 characters or fewer." }` / `{ "detail": "Email address must be 254 characters or fewer." }` (HTTP 400)
  - `{ "detail": "'<value>' is not a valid email address." }` (HTTP 400 — email mode only)
  - `{ "detail": "Pizza '<id>' not found in menu" }` (HTTP 400)
  - `{ "detail": "Too many requests. Please wait 5 seconds before trying again." }` (HTTP 429)
- **Rate Limited**: Yes (1 submission per IP per 5 seconds). The slot is consumed *before*
  validation, deliberately — refunding it on a validation failure would turn the endpoint into a
  free email-validation oracle. A rejected submission therefore also costs the caller the window.
- **Result**: Creates one order record per item; nothing is persisted if any item fails validation

---

## 10. Non-Functional Requirements

### 10.1 Performance
- **Session Limits**: Support up to 200 teams, 10 concurrent users per session
- **Response Time**: API endpoints respond within 500ms
- **Real-time Updates**: SSE updates delivered within 1 second of order change

### 10.2 Reliability
- **Data Persistence**: All orders and sessions survive container restarts
- **Session Timeout**: JWT tokens valid for 1 month; login required after expiry
- **Grace Period**: Enforce strict 2-minute grace period logic

### 10.3 Security
- **Password Storage**: Bcrypt hashing (minimum 10 rounds)
- **JWT**: HS256 algorithm, 1 month expiry
- **CORS**: Restrict to same-origin or configured domains
- **Input Validation**: Validate all user inputs (name length, price format, etc.)
- **SQL Injection**: N/A (no database), but sanitize file operations

### 10.4 Usability
- **Responsive Design**: Works on mobile (320px+), tablet, desktop
- **Accessibility**: Basic WCAG compliance (semantic HTML, alt text for images)
- **Error Messages**: Clear, actionable messages for users
- **Time Display**: Display session times clearly to team members

### 10.5 Maintainability
- **Code Structure**: Modular FastAPI application (routers, services, models)
- **Logging**: Log all authentication, session events, and errors
- **Documentation**: README with setup, deployment, and configuration instructions

---

## 11. Deployment

### 11.1 Docker Setup
```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 Volume Mounts
```bash
docker run \
  -v /path/to/config:/app/config \
  -v /path/to/data:/app/data \
  -p 8000:8000 \
  cpo-app
```

### 11.3 Configuration File (config.json)
```json
{
  "admin": {
    "username": "admin",
    "password_hash": "<bcrypt_hash>"
  },
  "cpos": [
    {
      "id": "<uuid>",
      "username": "john_doe",
      "email": "john@company.com",
      "password_hash": "<bcrypt_hash>",
      "team_name": "Engineering"
    }
  ]
}
```

---

## 12. Future Enhancements (Out of Scope)

- Database integration (PostgreSQL, MongoDB) for better scalability
- Multi-language support
- Email notifications to team members
- Integration with actual pizzeria APIs for ordering
- Payment processing
- Team member RSVP system
- Historical analytics and reporting

---

## Appendix: Constraints & Assumptions

| Item | Constraint | Rationale |
|------|-----------|-----------|
| Team Size | Max 200 teams | Manageable with file-based storage |
| Concurrent Users | Max 10 per session | Single container, file I/O bound |
| Session Duration | Typically 30 minutes | Pre-lunch ordering window |
| Grace Period | 2 minutes | Buffer for clock skew and network delays |
| Token Expiry | 1 month | Reasonable for internal teams |
| No Timezone Support | Single timezone | Simplification for prototype |
| No Inventory | Unlimited pizzas | Ordering, not fulfillment, system |
| No Real-time UI Refresh | Manual refresh button | Reduces complexity, SSE for push updates |
| Rate Limit Window | 5 seconds | Accounts for shared office IP, prevents spam |
| Quantity Per Order | Always 1 pizza | Simplified model, users add multiple pizzas via multiple order items |
| Session Link | Random alphanumeric (16+ chars) | Prevents guessing other teams' session links |
| IP Tracking in Summary | Client IP visible to CPO | Identifies coordinated spam patterns |
| Order Cancellation | CPO-only | Users cannot modify/cancel, full CPO control |

