'use client';
import React, { useState, useEffect, useRef } from 'react';
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { PushPreferences } from "@/lib/types";

export function PreferenceSliders() {
  const [prefs, setPrefs] = useState<Partial<PushPreferences>>({
    epsilon: 0.08,
    max_per_day: 10,
    quiet_start: 22,
    quiet_end: 8,
  });
  const [loading, setLoading] = useState(true);
  const saveTimeout = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadPrefs();
  }, []);

  const loadPrefs = async () => {
    try {
      const data = await apiClient.getPushPreferences(1);
      setPrefs(data);
    } catch (error) {
      toast.error("Failed to load preferences");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = (key: keyof PushPreferences, value: any) => {
    const newPrefs = { ...prefs, [key]: value };
    setPrefs(newPrefs);

    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(async () => {
      try {
        await apiClient.updatePushPreferences(1, { [key]: value });
        toast.success("Preferences saved");
      } catch (error) {
        toast.error("Failed to save preferences");
      }
    }, 800);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="space-y-8" data-testid="preference-sliders">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium">
            Exploration Ratio (ε)
          </Label>
          <span className="text-sm text-muted-foreground tabular-nums">
            {prefs.epsilon?.toFixed(2) ?? '0.08'}
          </span>
        </div>
        <Slider
          defaultValue={[prefs.epsilon ?? 0.08]}
          min={0.03}
          max={0.20}
          step={0.01}
          onValueChange={(vals) => handleUpdate('epsilon', vals[0])}
          data-testid="epsilon-slider"
        />
        <p className="text-xs text-muted-foreground">
          Current mode: {
            (prefs.epsilon ?? 0.08) <= 0.05 ? 'Conservative' :
            (prefs.epsilon ?? 0.08) <= 0.15 ? 'Balanced' : 'Exploratory'
          }
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-base font-medium">Daily Push Limit</Label>
          <span className="text-sm text-muted-foreground tabular-nums">
            {prefs.max_per_day ?? 10} items
          </span>
        </div>
        <Slider
          defaultValue={[prefs.max_per_day ?? 10]}
          min={1}
          max={50}
          step={1}
          onValueChange={(vals) => handleUpdate('max_per_day', vals[0])}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="quiet-start">Quiet Hours Start</Label>
          <Input
            id="quiet-start"
            type="number"
            min={0}
            max={23}
            value={prefs.quiet_start ?? 22}
            onChange={(e) => handleUpdate('quiet_start', parseInt(e.target.value))}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="quiet-end">Quiet Hours End</Label>
          <Input
            id="quiet-end"
            type="number"
            min={0}
            max={23}
            value={prefs.quiet_end ?? 8}
            onChange={(e) => handleUpdate('quiet_end', parseInt(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
