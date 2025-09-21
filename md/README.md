# Tarang Web Application

A web-based scientific computing platform for computational fluid dynamics and magnetohydrodynamics simulations. Converted from the original PyQt desktop application to run as a web service accessible via browser.

## 🌟 Features

- **Web-based Interface**: Access through any modern web browser
- **Real-time Monitoring**: Live simulation output via WebSocket connections
- **Multi-platform Support**: Run simulations locally or on remote HPC clusters
- **Scientific Computing**: Support for HYDRO, MHD, RBC, EULER, and SCALAR simulations
- **Data Analysis**: Built-in visualization and analysis tools
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Modern web browser
- AWS account (for deployment)

### Local Development
```bash
# Navigate to the project directory
cd Tarang-for-demo-main

# Run the local setup script
./run-local.sh
```

Access the application at `http://localhost:5000`

**Manual Setup (Alternative):**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r web_requirements.txt

# Run the application
python3 app.py
```

## 📋 Usage Workflow

1. **Login** - Use any credentials (authentication simplified for demo)
2. **Home Page** - Choose "Create New Run" or "Analyze Data"
3. **Configuration** - Set simulation parameters through multi-step wizard:
   - Machine selection (Local/Benard/AMD)
   - Grid dimensions and simulation type
   - Physics-specific parameters (HYDRO/MHD)
   - Time and output settings
4. **Run Simulation** - Monitor real-time output and control execution
5. **Analyze Data** - Generate plots and visualizations

## 🔧 Simulation Types

- **HYDRO** - Hydrodynamic simulations (fluid flow)
- **MHD** - Magnetohydrodynamics (fluid flow with magnetic fields)
- **RBC** - Rayleigh-Bénard Convection (thermal convection)
- **EULER** - Euler equations for fluid dynamics
- **COARSEN** - Grid coarsening operations
- **SCALAR** - Scalar field simulations

## 📁 Project Structure

See [APPLICATION_STRUCTURE.md](APPLICATION_STRUCTURE.md) for detailed architecture documentation.

## 🌐 AWS Deployment

See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for complete production deployment guide.

## 🔒 Security Notes

- Change the `SECRET_KEY` in production
- Implement proper user authentication for production use
- Use valid SSL certificates
- Configure firewall rules appropriately

## 📊 System Requirements

- **Development**: Python 3.9+, 4GB RAM
- **Production**: t3.medium EC2 instance or equivalent
- **Dependencies**: NumPy, Flask, SocketIO, scientific computing libraries

## 🛠️ Troubleshooting

### Common Issues:
- **Port conflicts**: Ensure port 5000 is available
- **Permission issues**: Check file ownership and Python environment
- **Memory issues**: Consider upgrading instance size for large simulations

### Useful Commands:
```bash
# Check application status
ps aux | grep app.py

# View logs
tail -f logs/app.log

# Restart application
pkill -f app.py
python3 app.py
```

## 📞 Support

For issues and questions, refer to the original Tarang documentation or contact the development team.

## 📄 License

This project maintains the same license as the original Tarang application.
