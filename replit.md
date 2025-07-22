# Telegram Protection Bot

## Overview

This is a comprehensive Telegram group protection bot built with Python and Pyrogram. The bot provides advanced moderation features including content filtering, anti-flood protection, message monitoring, and administrative controls. It's designed to automatically detect and moderate inappropriate content, spam, and other violations in Telegram groups. The bot is currently deployed and running as `@Groupgardian_robot`.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes (July 22, 2025)

✓ Complete bot implementation with all core security features
✓ Telegram API integration successfully configured  
✓ SQLite database with comprehensive schema for logging and settings
✓ Multi-language keyword filtering (English, Hindi)
✓ Advanced spam detection with scoring algorithm
✓ Edit message monitoring and automatic deletion
✓ Anti-flood protection with user restrictions
✓ Admin panel with inline keyboard controls
✓ Comprehensive audit logging and export functionality
✓ Bot successfully deployed and running as @Groupgardian_robot

**MAJOR UPDATE: Production-Ready Enterprise Features Added**
✓ Advanced captcha verification system (text, math, button, voice)
✓ Comprehensive anti-spam system with disposable number detection
✓ Global ban (GBAN) system for cross-group user management
✓ Role-based permission system (Owner, Admin, Trusted, Muted)
✓ Welcome/farewell system with media support and verification
✓ Enhanced handlers integrating all protection features
✓ Group locking and advanced moderation commands
✓ Production deployment documentation for 10,000+ groups
✓ Performance optimization and scaling configurations
✓ Enterprise-grade security and monitoring setup

## System Architecture

### Core Architecture
The bot follows a modular architecture with clear separation of concerns:

- **Client Layer**: Pyrogram-based Telegram client for API interactions
- **Handler Layer**: Event-driven message processing system
- **Service Layer**: Business logic for moderation, filtering, and administration
- **Data Layer**: SQLite database for persistent storage
- **Configuration Layer**: Environment-based configuration management

### Key Design Patterns
- **Factory Pattern**: Used for handler setup and initialization
- **Strategy Pattern**: Implemented in content filtering system
- **Observer Pattern**: Event-driven message handling
- **Singleton Pattern**: Database connection management

## Key Components

### 1. Main Application (`main.py`)
- **Purpose**: Entry point and bot lifecycle management
- **Responsibilities**: Initialize components, start bot, handle shutdown
- **Architecture**: Centralized initialization with dependency injection

### 2. Message Handlers (`handlers.py`)
- **Purpose**: Process incoming messages and events
- **Features**: Text filtering, media validation, flood protection
- **Architecture**: Decorator-based event handlers with filtering

### 3. Content Filter (`filters.py`)
- **Purpose**: Detect inappropriate content using keyword matching
- **Features**: Regex-based pattern matching, category-based filtering
- **Architecture**: Compiled pattern cache for performance

### 4. Database Layer (`database.py`)
- **Purpose**: Data persistence and retrieval
- **Technology**: SQLite with aiosqlite for async operations
- **Schema**: Groups, users, moderation logs, settings

### 5. Admin Panel (`admin.py`)
- **Purpose**: Administrative interface for bot configuration
- **Features**: Inline keyboard menus, settings management
- **Architecture**: Callback-based menu system

### 6. Logging System (`logger.py`)
- **Purpose**: Audit trail and violation tracking
- **Features**: Structured logging, retention policies
- **Architecture**: Centralized logging with database integration

### 7. Configuration Management (`config.py`)
- **Purpose**: Environment-based configuration
- **Features**: Validation, type conversion, defaults
- **Architecture**: Class-based configuration with environment variables

### 8. Utilities (`utils.py`)
- **Purpose**: Common helper functions
- **Features**: Permission checking, user info extraction
- **Architecture**: Stateless utility functions

## Data Flow

### Message Processing Flow
1. **Message Reception**: Pyrogram handlers receive messages
2. **User/Group Registration**: Add entities to database if new
3. **Permission Check**: Verify user admin status
4. **Content Analysis**: Apply filters and detect violations
5. **Action Execution**: Delete, warn, or ban based on violation
6. **Logging**: Record moderation actions for audit

### Admin Panel Flow
1. **Command Reception**: Admin issues command
2. **Permission Verification**: Check admin privileges
3. **Menu Display**: Show relevant options via inline keyboard
4. **Setting Updates**: Modify configuration based on selection
5. **Database Persistence**: Store changes to database

## External Dependencies

### Core Libraries
- **Pyrogram**: Telegram MTProto API client
- **aiosqlite**: Async SQLite database operations
- **python-dotenv**: Environment variable management

### Python Standard Library
- **asyncio**: Asynchronous programming
- **logging**: Structured logging
- **re**: Regular expression matching
- **json**: Configuration file parsing
- **datetime**: Time-based operations

### Configuration Files
- **keywords.json**: Banned content keywords by category
- **.env**: Environment variables (API keys, settings)
- **bot_data.db**: SQLite database file

## Deployment Strategy

### Environment Setup
- **Development**: Local environment with file-based configuration
- **Production**: Environment variables for sensitive data
- **Database**: SQLite for simplicity (can be upgraded to PostgreSQL)

### Configuration Management
- **API Credentials**: Environment variables (API_ID, API_HASH, BOT_TOKEN)
- **Feature Toggles**: Boolean environment variables
- **Thresholds**: Integer environment variables with defaults
- **Keywords**: JSON file for easy updates

### Scaling Considerations
- **Database**: Currently SQLite, can migrate to PostgreSQL for multi-instance deployments
- **Caching**: In-memory pattern compilation for performance
- **Logging**: File-based with rotation for disk space management

### Security Measures
- **Admin Verification**: Multiple levels of permission checking
- **Input Validation**: Sanitization of user inputs
- **Rate Limiting**: Flood protection mechanisms
- **Audit Logging**: Complete moderation action history

The bot is designed to be easily deployable on platforms like Replit, with minimal configuration required. The modular architecture allows for easy extension and maintenance.