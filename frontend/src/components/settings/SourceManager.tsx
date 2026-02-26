'use client';
import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { Source } from "@/lib/types";
import { Trash2, Plus } from "lucide-react";

export function SourceManager() {
  const [sources, setSources] = useState<Source[]>([]);
  const [newSource, setNewSource] = useState({ name: '', url: '', type: 'rss' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSources();
  }, []);

  const loadSources = async () => {
    try {
      const data = await apiClient.getSources();
      setSources(data);
    } catch (error) {
      toast.error("Failed to load sources");
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSource.name || !newSource.url) return;
    setLoading(true);
    try {
      await apiClient.createSource(newSource);
      toast.success("Source added");
      setNewSource({ name: '', url: '', type: 'rss' });
      loadSources();
    } catch (error) {
      toast.error("Failed to add source");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.deleteSource(id);
      toast.success("Source deleted");
      setSources(sources.filter(s => s.id !== id));
    } catch (error) {
      toast.error("Failed to delete source");
    }
  };

  return (
    <div className="space-y-6" data-testid="source-manager">
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-6">
        <h3 className="text-lg font-semibold mb-4">Add New Source</h3>
        <form onSubmit={handleAdd} className="flex gap-4 items-end">
          <div className="grid w-full gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="TechCrunch"
              value={newSource.name}
              onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
              data-testid="source-name"
            />
          </div>
          <div className="grid w-full gap-1.5">
            <Label htmlFor="url">RSS / arXiv URL</Label>
            <Input
              id="url"
              placeholder="https://techcrunch.com/feed/"
              value={newSource.url}
              onChange={(e) => setNewSource({ ...newSource, url: e.target.value })}
              data-testid="source-url"
            />
          </div>
          <Button type="submit" disabled={loading} data-testid="add-source">
            <Plus className="w-4 h-4 mr-2" />
            Add
          </Button>
        </form>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Active Sources</h3>
        {sources.length === 0 ? (
          <p className="text-muted-foreground">No sources configured.</p>
        ) : (
          <div className="grid gap-4">
            {sources.map((source) => (
              <div
                key={source.id}
                className="flex items-center justify-between p-4 rounded-lg border bg-card"
                data-testid="source-list-item"
              >
                <div className="grid gap-1">
                  <div className="font-medium">{source.name}</div>
                  <div className="text-sm text-muted-foreground truncate max-w-[300px] md:max-w-[500px]">
                    {source.url}
                  </div>
                  <div className="text-xs text-muted-foreground capitalize bg-secondary px-2 py-0.5 rounded w-fit">
                    {source.type}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(source.id)}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
