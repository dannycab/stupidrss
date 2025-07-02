# StupidRSS Docker Deployment

This directory contains Docker configuration for deploying StupidRSS.

## Quick Start

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the application:**
   - Main app: http://localhost:8000/app
   - Documentation: http://localhost:8000/
   - Admin panel: http://localhost:8000/admin

## Docker Commands

### Development
```bash
# Build and start in foreground (with logs)
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild image
docker-compose build --no-cache
```

### Production
```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# Update application
git pull
docker-compose build
docker-compose up -d

# Backup database
docker-compose exec stupidrss cp /app/data/rss_reader.db /app/data/backup_$(date +%Y%m%d_%H%M%S).db
```

## Configuration

### Environment Variables
You can customize the application by setting environment variables in a `.env` file:

```env
# Database location
DATABASE_URL=sqlite:///data/rss_reader.db

# Server configuration
HOST=0.0.0.0
PORT=8000

# Application settings
DEBUG=false
```

### Data Persistence
The database is stored in the `./data` directory on the host, which is mounted as a volume. This ensures your feeds and articles persist across container restarts.

### Port Configuration
By default, the application runs on port 8000. To change this, modify the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "3000:8000"  # Maps host port 3000 to container port 8000
```

## Health Checks
The container includes health checks that verify the application is responding correctly. You can check the health status with:

```bash
docker-compose ps
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs stupidrss

# Check if port is already in use
lsof -i :8000
```

### Database issues
```bash
# Access container shell
docker-compose exec stupidrss bash

# Check database file
ls -la /app/data/

# Reset database (will lose all data!)
docker-compose down
rm -f ./data/rss_reader.db
docker-compose up -d
```

### Performance tuning
For production deployments, consider:

1. **Resource limits** in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '0.5'
   ```

2. **Reverse proxy** (nginx, traefik) for SSL and caching

3. **External database** (PostgreSQL) for better performance

## Security Notes

- The application runs as a non-root user inside the container
- Database files are stored in a mounted volume with appropriate permissions
- No sensitive data is exposed in environment variables
- Health checks ensure the service is running correctly

## Backup Strategy

Regular backups of the database:
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T stupidrss cp /app/data/rss_reader.db /app/data/backup_$DATE.db
echo "Backup created: backup_$DATE.db"
EOF

chmod +x backup.sh

# Run daily via cron
0 2 * * * /path/to/stupidrss/backup.sh
```
