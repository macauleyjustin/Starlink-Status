#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QSystemTrayIcon>
#include <QLabel>
#include <QMenu>
#include "starlinkclient.h"

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

protected:
    void closeEvent(QCloseEvent *event) override;

private slots:
    void updateStatus(bool connected);
    void updateSpeed(float downloadMbps, float uploadMbps, float latencyMs);
    void updateLocation(double lat, double lon, double alt);
    void updateSatelliteInfo(const QString &id, const QString &hardwareVersion);
    void onTrayIconActivated(QSystemTrayIcon::ActivationReason reason);

private:
    void createTrayIcon();
    void createUi();

    StarlinkClient *client_;
    QSystemTrayIcon *trayIcon_;
    QMenu *trayIconMenu_;

    QLabel *statusLabel_;
    QLabel *speedLabel_;
    QLabel *locationLabel_;
    QLabel *satelliteLabel_;
    
    QIcon connectedIcon_;
    QIcon disconnectedIcon_;
};

#endif // MAINWINDOW_H
