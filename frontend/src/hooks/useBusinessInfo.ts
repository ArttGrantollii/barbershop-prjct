import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"

export interface BusinessInfo {
  name: string
  timezone: string
}

export function useBusinessInfo() {
  return useQuery<BusinessInfo>({
    queryKey: ["business-info"],
    queryFn: async () => (await api.get("/api/v1/business-info")).data,
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
