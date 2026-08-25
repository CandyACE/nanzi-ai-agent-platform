import { ref } from "vue";
import axios from "@/utils/axios";
import type { DataPortalHomePayload, DataPortalReportItem, DataPortalScenePayload } from "@/types/dataPortal";

export function useDataPortalHome() {
  const homePayload = ref<DataPortalHomePayload | null>(null);
  const scenePayload = ref<DataPortalScenePayload | null>(null);
  const allReports = ref<DataPortalReportItem[]>([]);
  const homeLoading = ref(false);
  const sceneLoading = ref(false);
  const reportsLoading = ref(false);
  const homeError = ref("");
  const sceneError = ref("");
  const reportsError = ref("");

  const requestHome = async () => {
    const response = await axios.get("/api/portal/data-portal/home");
    return response.data?.data as DataPortalHomePayload;
  };

  const requestScenes = async (refresh = false) => {
    const response = await axios.get("/api/v1/chat/dataset-menu", {
      params: refresh ? { refresh: true } : undefined,
    });
    return response.data?.data as DataPortalScenePayload;
  };

  const requestReports = async () => {
    const response = await axios.get("/api/portal/saved-reports", { params: { scope: "all" } });
    return (response.data?.data || []) as DataPortalReportItem[];
  };

  const load = async (refresh = false) => {
    homeLoading.value = true;
    sceneLoading.value = true;
    reportsLoading.value = true;
    homeError.value = "";
    sceneError.value = "";
    reportsError.value = "";

    const homeTask = requestHome()
      .then((payload) => {
        homePayload.value = payload;
      })
      .catch(() => {
        homeError.value = "首页运行数据暂时无法获取";
      })
      .finally(() => {
        homeLoading.value = false;
      });
    const sceneTask = requestScenes(refresh)
      .then((payload) => {
        scenePayload.value = payload;
      })
      .catch(() => {
        sceneError.value = "推荐场景暂时无法获取";
      })
      .finally(() => {
        sceneLoading.value = false;
      });
    const reportsTask = requestReports()
      .then((reports) => {
        allReports.value = reports;
      })
      .catch(() => {
        reportsError.value = "完整报表列表暂时无法获取";
      })
      .finally(() => {
        reportsLoading.value = false;
      });

    await Promise.all([homeTask, sceneTask, reportsTask]);
  };

  const refresh = () => load(true);

  return {
    homePayload,
    scenePayload,
    allReports,
    homeLoading,
    sceneLoading,
    reportsLoading,
    homeError,
    sceneError,
    reportsError,
    load,
    refresh,
  };
}
