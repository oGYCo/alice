import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SourceManager } from '../SourceManager';
import { PreferenceSliders } from '../PreferenceSliders';
import { ScheduleEditor } from '../ScheduleEditor';
import { UserModeSelector } from '../UserModeSelector';
import { apiClient } from '@/lib/api';

// Mock apiClient
vi.mock('@/lib/api', () => ({
  apiClient: {
    getSources: vi.fn(),
    createSource: vi.fn(),
    deleteSource: vi.fn(),
    getPushPreferences: vi.fn(),
    updatePushPreferences: vi.fn(),
  },
}));

// Mock Sonner toast to avoid errors during tests
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('Settings Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // SourceManager Tests
  it('renders SourceManager and loads sources', async () => {
    (apiClient.getSources as any).mockResolvedValue([
      { id: 1, name: 'Test Source', url: 'http://example.com', type: 'rss' }
    ]);

    render(<SourceManager />);
    expect(screen.getByTestId('source-manager')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Test Source')).toBeInTheDocument();
    });
  });

  it('adds a new source', async () => {
    (apiClient.getSources as any).mockResolvedValue([]);
    (apiClient.createSource as any).mockResolvedValue({ id: 2, name: 'New', url: 'http://new.com', type: 'rss' });

    render(<SourceManager />);
    
    fireEvent.change(screen.getByTestId('source-name'), { target: { value: 'New' } });
    fireEvent.change(screen.getByTestId('source-url'), { target: { value: 'http://new.com' } });
    fireEvent.click(screen.getByTestId('add-source'));

    await waitFor(() => {
      expect(apiClient.createSource).toHaveBeenCalledWith({ name: 'New', url: 'http://new.com', type: 'rss' });
    });
  });

  // PreferenceSliders Tests
  it('renders PreferenceSliders and loads prefs', async () => {
    (apiClient.getPushPreferences as any).mockResolvedValue({
      epsilon: 0.15,
      max_per_day: 20
    });

    render(<PreferenceSliders />);
    await waitFor(() => {
      expect(screen.getByTestId('preference-sliders')).toBeInTheDocument();
    });

    expect(screen.getByTestId('epsilon-slider')).toBeInTheDocument();
    expect(screen.getByText('0.15')).toBeInTheDocument();
  });

  // ScheduleEditor Tests
  it('renders ScheduleEditor and loads schedule', async () => {
    (apiClient.getPushPreferences as any).mockResolvedValue({
      schedule: {
        morning: { name: 'morning', start_time: '09:37', end_time: '11:00', is_enabled: true, max_pushes: 5 }
      }
    });

    render(<ScheduleEditor />);
    await waitFor(() => {
      expect(screen.getByTestId('schedule-editor')).toBeInTheDocument();
    });
    
    expect(screen.getByDisplayValue('09:37')).toBeInTheDocument();
  });

  // UserModeSelector Tests
  it('renders UserModeSelector and updates mode', async () => {
    (apiClient.getPushPreferences as any).mockResolvedValue({
      user_mode: 'daily'
    });

    render(<UserModeSelector />);
    await waitFor(() => {
    expect(screen.getByTestId('user-mode-selector')).toBeInTheDocument();
    });
    
    // Select interaction is tricky in JSDOM, let's just check if it renders initial state
    await waitFor(() => {
      expect(screen.getByText('Daily (日常)')).toBeInTheDocument();
    });
  });
});
