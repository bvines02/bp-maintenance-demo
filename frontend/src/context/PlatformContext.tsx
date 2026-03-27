import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface PlatformInfo {
  name: string;
  code: string;
  description: string;
}

interface PlatformContextType {
  platforms: PlatformInfo[];
  selected: string[];   // names of selected platforms
  setSelected: (names: string[]) => void;
  toggle: (name: string) => void;
  selectAll: () => void;
  platformsParam: string | undefined;  // comma-separated for API calls, undefined = all
}

const PlatformContext = createContext<PlatformContextType>({
  platforms: [],
  selected: [],
  setSelected: () => {},
  toggle: () => {},
  selectAll: () => {},
  platformsParam: undefined,
});

export function PlatformProvider({ children }: { children: ReactNode }) {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    axios.get(`${API_BASE}/platforms`).then(r => {
      const data: PlatformInfo[] = r.data;
      setPlatforms(data);
      setSelected(data.map(p => p.name));  // all selected by default
    }).catch(() => {});
  }, []);

  const toggle = (name: string) => {
    setSelected(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const selectAll = () => setSelected(platforms.map(p => p.name));

  // If all platforms selected (or none loaded yet), don't send filter
  const allSelected = platforms.length > 0 && selected.length === platforms.length;
  const platformsParam = allSelected || selected.length === 0
    ? undefined
    : selected.join(",");

  return (
    <PlatformContext.Provider value={{ platforms, selected, setSelected, toggle, selectAll, platformsParam }}>
      {children}
    </PlatformContext.Provider>
  );
}

export function usePlatforms() {
  return useContext(PlatformContext);
}
