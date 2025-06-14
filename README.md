# FastAPI Authentication System

A professional authentication system built with FastAPI and MongoDB, featuring user registration, login, and JWT-based authentication with a well-organized project structure.

## ✨ Features

- ✅ **User Registration & Login** - Secure account creation and authentication
- ✅ **JWT Authentication** - Stateless token-based authentication
- ✅ **Password Security** - Bcrypt hashing for password storage
- ✅ **MongoDB Integration** - Async database operations with Motor
- ✅ **Input Validation** - Pydantic models with comprehensive validation
- ✅ **Protected Routes** - Authentication middleware for secure endpoints
- ✅ **Professional Structure** - Organized codebase following FastAPI best practices
- ✅ **Auto-generated Documentation** - Swagger UI and ReDoc integration
- ✅ **Configuration Management** - Environment-based settings with Pydantic

## 🏗️ Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application and configuration
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Application settings and configuration
│   │   └── security.py           # Authentication and security utilities
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py               # Pydantic models for users
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py               # Authentication endpoints
│   │   └── protected.py          # Protected route examples
│   └── database/
│       ├── __init__.py
│       └── mongodb.py            # Database connection and configuration
├── start.py                       # Server startup script
├── requirements.txt               # Python dependencies
├── .env                          # Environment variables (create this)
└── README.md                     # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```env
# Database Configuration
MONGODB_URL=mongodb+srv://effinfinefriday:zoK7WFMVzhCpwWyH@cluster0.iawq3rz.mongodb.net/
DATABASE_NAME=fastapi_auth_db

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production-please
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# CORS Configuration (comma-separated list)
CORS_ORIGINS=["*"]
```

### 3. Start the Server

```bash
python start.py
```

The server will be available at:
- **API**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **Alternative Documentation**: http://localhost:8000/redoc

## 📚 API Documentation

### Base URL
All API endpoints are prefixed with `/api/v1`

### Authentication Endpoints

#### Register User
**POST** `/api/v1/auth/register`

Create a new user account.

```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

#### Login User
**POST** `/api/v1/auth/login`

Authenticate user and receive JWT token.

```json
{
  "username": "johndoe",
  "password": "securepassword123"
}
```

#### Get Current User
**GET** `/api/v1/auth/me`

Get authenticated user information (requires JWT token).

**Headers:**
```
Authorization: Bearer {your_jwt_token}
```

### Protected Endpoints

#### User Profile
**GET** `/api/v1/protected/profile`

Get detailed user profile information.

#### User Dashboard
**GET** `/api/v1/protected/dashboard`

Get user dashboard data with statistics.

#### User Settings
**GET** `/api/v1/protected/settings`

Get user preferences and settings.

## 🔒 Authentication Flow

1. **Register**: Create account with `/api/v1/auth/register`
2. **Login**: Authenticate with `/api/v1/auth/login` to receive JWT token
3. **Access Protected Routes**: Include JWT in `Authorization: Bearer <token>` header
4. **Token Expiry**: Tokens expire after 30 minutes (configurable)

## 🧪 Testing the API

### Using curl

1. **Register a new user:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User"
  }'
```

2. **Login:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpassword123"
  }'
```

3. **Access protected route:**
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

### Using the Interactive Documentation

Visit http://localhost:8000/docs for the Swagger UI where you can:
- Test all endpoints interactively
- View request/response schemas
- Authenticate and test protected routes
- Download OpenAPI specifications

## ⚙️ Configuration

The application uses Pydantic Settings for configuration management. All settings can be configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | **Required** |
| `DATABASE_NAME` | Database name | `fastapi_auth_db` |
| `JWT_SECRET_KEY` | Secret key for JWT signing | **Change in production!** |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `30` |
| `SERVER_HOST` | Server host | `0.0.0.0` |
| `SERVER_PORT` | Server port | `8000` |
| `CORS_ORIGINS` | Allowed CORS origins | `["*"]` |

## 🔐 Security Features

- **Password Hashing**: Bcrypt with automatic salt generation
- **JWT Tokens**: Secure, stateless authentication
- **Input Validation**: Comprehensive validation with Pydantic
- **CORS Protection**: Configurable cross-origin request handling
- **Environment Variables**: Sensitive data stored securely
- **Database Security**: Parameterized queries prevent injection attacks

## 🏃‍♀️ Development

The application includes:
- **Auto-reload**: Server automatically restarts on code changes
- **Comprehensive Logging**: Detailed logging for debugging
- **Error Handling**: Proper HTTP status codes and error messages
- **Type Hints**: Full type annotation for better IDE support
- **Async/Await**: Fully asynchronous for better performance

## 🚀 Production Deployment

### Security Checklist

1. **Set a strong JWT secret key**
   ```env
   JWT_SECRET_KEY=your-super-long-random-secret-key-here
   ```

2. **Configure specific CORS origins**
   ```env
   CORS_ORIGINS=["https://yourdomain.com", "https://app.yourdomain.com"]
   ```

3. **Use a production WSGI server** like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

4. **Set up proper logging and monitoring**

5. **Configure database indexes** for better performance:
   ```javascript
   // In MongoDB
   db.users.createIndex({ "username": 1 }, { unique: true })
   db.users.createIndex({ "email": 1 }, { unique: true })
   ```

### Environment Variables for Production

```env
# Production environment
JWT_SECRET_KEY=your-production-secret-key-very-long-and-random
CORS_ORIGINS=["https://yourdomain.com"]
SERVER_HOST=127.0.0.1
ACCESS_TOKEN_EXPIRE_MINUTES=15
```

## 📝 License

This project is open source and available under the [MIT License](https://opensource.org/licenses/MIT).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support and questions, please [open an issue](https://github.com/yourusername/fastapi-auth/issues) on GitHub. 