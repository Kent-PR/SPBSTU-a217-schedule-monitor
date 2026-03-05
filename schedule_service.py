import win32serviceutil
import win32service
import win32event
import servicemanager
import time
import logging

from main import run_check  # твоя функция проверки расписания

class ScheduleService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ScheduleMonitorService"
    _svc_display_name_ = "Schedule Monitor Service"
    _svc_description_ = "Monitoring changes in the SPBSTU A.2.17 schedule"

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        logging.info("Service stopping...")
        self.running = False
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        servicemanager.LogInfoMsg(f"{self._svc_name_} stopping")

    def SvcDoRun(self):
        logging.info("Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        # ⚡ сервис готов и работает
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogInfoMsg(f"{self._svc_name_} successfully started")
        logging.info("Service started")

        # основной цикл прямо здесь
        while self.running:
            try:
                run_check()  # твоя проверка расписаний
            except Exception:
                logging.exception("Error in service loop")

            # проверка каждые 10 минут
            for _ in range(600):
                if not self.running:
                    break
                time.sleep(1)

        logging.info("Service stopped")
        servicemanager.LogInfoMsg(f"{self._svc_name_} stopped")


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(ScheduleService)