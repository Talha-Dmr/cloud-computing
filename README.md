# IoT Platform - Microservices Project

A comprehensive IoT Platform built with microservices architecture, demonstrating modern cloud-native development practices.

## 🏗️ Architecture Overview

This project implements a full-stack IoT platform with the following microservices:

- **Device Registry Service** - Device registration and management
- **Data Ingestion Service** - Real-time sensor data collection
- **Alert Engine** - Rule-based alerting system
- **User Management** - Authentication and authorization
- **Notification Service** - Multi-channel notifications
- **API Gateway** - Single entry point with authentication

## 🛠️ Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Databases**: PostgreSQL, InfluxDB, Redis
- **Message Queue**: Apache Kafka, RabbitMQ
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes (local)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus, Grafana
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+
- Node.js 18+ (for frontend)
- kubectl and kind (for local Kubernetes)

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/your-username/iot-platform.git
cd iot-platform
```

2. Start services with Docker Compose:
```bash
make dev
```

3. Run tests:
```bash
make test
```

### Kubernetes Deployment

1. Create local cluster:
```bash
make create-cluster
```

2. Deploy services:
```bash
make deploy
```

3. Access services:
```bash
make forward
```

## 📊 Services

### Device Registry Service
- **Port**: 8001
- **Database**: PostgreSQL
- **Features**: Device CRUD operations, authentication, metadata management

### Data Ingestion Service
- **Port**: 8002
- **Protocols**: HTTP, MQTT
- **Features**: Real-time data processing, Kafka integration, data validation

### Alert Engine
- **Port**: 8003
- **Database**: Redis (caching)
- **Features**: Rule processing, alert generation, WebSocket notifications

### API Gateway
- **Port**: 8000
- **Features**: Request routing, JWT authentication, rate limiting

## 📈 Monitoring

Access monitoring dashboards:
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Kibana**: http://localhost:5601

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Load tests
locust -f tests/load/locustfile.py
```

## 📚 Documentation

- [API Documentation](docs/api/README.md)
- [Architecture Guide](docs/architecture/README.md)
- [Deployment Guide](docs/deployment/README.md)

## 👥 Team

- Backend Developer - Core microservices
- DevOps Engineer - Kubernetes, CI/CD
- Frontend Developer - Dashboard UI
- QA Engineer - Testing automation
- Tech Lead - Architecture & review

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🎯 Project Requirements

✅ Microservices architecture
✅ Docker containerization
✅ Kubernetes deployment
✅ CI/CD pipeline
✅ Monitoring and logging
✅ Comprehensive testing
✅ Documentation