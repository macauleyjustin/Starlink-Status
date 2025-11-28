#include "mainwindow.h"
#include <QVBoxLayout>
#include <QCloseEvent>
#include <QApplication>
#include <QAction>
#include <QMessageBox>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent), client_(new StarlinkClient(this))
{
    createUi();
    createTrayIcon();

    connect(client_, &StarlinkClient::statusChanged, this, &MainWindow::updateStatus);
    connect(client_, &StarlinkClient::speedUpdated, this, &MainWindow::updateSpeed);
    connect(client_, &StarlinkClient::locationUpdated, this, &MainWindow::updateLocation);
    connect(client_, &StarlinkClient::satelliteInfoUpdated, this, &MainWindow::updateSatelliteInfo);

    client_->startMonitoring();
    
    // Load icons (placeholders for now, will be replaced by generated images)
    connectedIcon_ = QIcon(":/icons/connected.png");
    disconnectedIcon_ = QIcon(":/icons/disconnected.png");
    
    updateStatus(false); // Initial state
}

MainWindow::~MainWindow()
{
}

void MainWindow::createUi()
{
    QWidget *centralWidget = new QWidget(this);
    QVBoxLayout *layout = new QVBoxLayout(centralWidget);

    statusLabel_ = new QLabel("Status: Connecting...", this);
    speedLabel_ = new QLabel("Speed: --", this);
    locationLabel_ = new QLabel("Location: --", this);
    satelliteLabel_ = new QLabel("Satellite: --", this);

    layout->addWidget(statusLabel_);
    layout->addWidget(speedLabel_);
    layout->addWidget(locationLabel_);
    layout->addWidget(satelliteLabel_);

    setCentralWidget(centralWidget);
    setWindowTitle("Starlink Monitor");
    resize(300, 200);
}

void MainWindow::createTrayIcon()
{
    trayIconMenu_ = new QMenu(this);
    
    QAction *restoreAction = new QAction("Show", this);
    connect(restoreAction, &QAction::triggered, this, &MainWindow::showNormal);
    trayIconMenu_->addAction(restoreAction);

    QAction *quitAction = new QAction("Quit", this);
    connect(quitAction, &QAction::triggered, qApp, &QCoreApplication::quit);
    trayIconMenu_->addAction(quitAction);

    trayIcon_ = new QSystemTrayIcon(this);
    trayIcon_->setContextMenu(trayIconMenu_);
    
    connect(trayIcon_, &QSystemTrayIcon::activated, this, &MainWindow::onTrayIconActivated);
    
    trayIcon_->show();
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    if (trayIcon_->isVisible()) {
        hide();
        event->ignore();
    }
}

void MainWindow::onTrayIconActivated(QSystemTrayIcon::ActivationReason reason)
{
    if (reason == QSystemTrayIcon::Trigger || reason == QSystemTrayIcon::DoubleClick) {
        if (isVisible()) {
            hide();
        } else {
            showNormal();
            activateWindow();
        }
    }
}

void MainWindow::updateStatus(bool connected)
{
    if (connected) {
        statusLabel_->setText("Status: Connected");
        trayIcon_->setIcon(connectedIcon_);
        trayIcon_->setToolTip("Starlink: Connected");
    } else {
        statusLabel_->setText("Status: Disconnected");
        trayIcon_->setIcon(disconnectedIcon_);
        trayIcon_->setToolTip("Starlink: Disconnected");
    }
}

void MainWindow::updateSpeed(float downloadMbps, float uploadMbps, float latencyMs)
{
    speedLabel_->setText(QString("Down: %1 Mbps | Up: %2 Mbps | Ping: %3 ms")
                         .arg(downloadMbps, 0, 'f', 1)
                         .arg(uploadMbps, 0, 'f', 1)
                         .arg(latencyMs, 0, 'f', 0));
}

void MainWindow::updateLocation(double lat, double lon, double alt)
{
    locationLabel_->setText(QString("Lat: %1 | Lon: %2 | Alt: %3 m")
                            .arg(lat, 0, 'f', 4)
                            .arg(lon, 0, 'f', 4)
                            .arg(alt, 0, 'f', 1));
}

void MainWindow::updateSatelliteInfo(const QString &id, const QString &hardwareVersion)
{
    satelliteLabel_->setText(QString("ID: %1 | HW: %2").arg(id).arg(hardwareVersion));
}
