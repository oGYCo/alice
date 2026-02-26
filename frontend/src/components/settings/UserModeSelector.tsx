import React, { useState, useEffect, useRef } from 'react';
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { UserMode } from "@/lib/types";

const MODES: { value: UserMode; label: string; description: string }[] = [
  { value: 'daily', label: 'Daily (日常)', description: 'Standard balanced mode' },
  { value: 'project', label: 'Project Focus (项目攻关)', description: 'Intense focus on specific topics' },
  { value: 'explore', label: 'Exploration (探索)', description: 'High variety, breaking information bubbles' },
  { value: 'low_energy', label: 'Low Energy (低能量)', description: 'Easy to consume, inspiring content' },
];

export function UserModeSelector() {
  const [mode, setMode] = useState<UserMode>('daily');
  const [projectDesc, setProjectDesc] = useState('');
  const [loading, setLoading] = useState(true);
  const saveTimeout = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadPrefs();
  }, []);

  const loadPrefs = async () => {
    try {
      const data = await apiClient.getPushPreferences(1);
      if (data.user_mode) setMode(data.user_mode);
      if (data.project_description) setProjectDesc(data.project_description);
    } catch (error) {
      toast.error("Failed to load user mode");
    } finally {
      setLoading(false);
    }
  };

  const saveUpdates = async (updates: { user_mode?: UserMode; project_description?: string }) => {
    try {
      await apiClient.updatePushPreferences(1, updates);
      toast.success("Mode updated");
    } catch (error) {
      toast.error("Failed to save mode");
    }
  };

  const handleModeChange = (newMode: UserMode) => {
    setMode(newMode);
    saveUpdates({ user_mode: newMode, project_description: projectDesc });
  };

  const handleDescChange = (newDesc: string) => {
    setProjectDesc(newDesc);
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      saveUpdates({ user_mode: mode, project_description: newDesc });
    }, 800);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="space-y-6" data-testid="user-mode-selector">
      <div className="space-y-4">
        <Label>Current Mode</Label>
        <Select value={mode} onValueChange={(val) => handleModeChange(val as UserMode)}>
          <SelectTrigger className="w-full md:w-[300px]">
            <SelectValue placeholder="Select mode" />
          </SelectTrigger>
          <SelectContent>
            {MODES.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {MODES.find(m => m.value === mode)?.description}
        </p>
      </div>

      {mode === 'project' && (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <Label htmlFor="project-desc">Project Description</Label>
          <Textarea
            id="project-desc"
            placeholder="Describe what you are working on (e.g., 'Learning Rust async programming' or 'Researching LLM agents')..."
            value={projectDesc}
            onChange={(e) => handleDescChange(e.target.value)}
            className="min-h-[100px]"
          />
          <p className="text-xs text-muted-foreground">
            Alice will prioritize content related to this project.
          </p>
        </div>
      )}
    </div>
  );
}
