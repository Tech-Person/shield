import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from './ui/dialog';
import { AlertTriangle } from 'lucide-react';

export default function ChangePasswordDialog({ open, onOpenChange, forced = false }) {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Please fill all fields');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    
    if (newPassword.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setIsLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      toast.success('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      onOpenChange(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenChange = (newOpen) => {
    // Prevent closing if forced
    if (forced && !newOpen) {
      return;
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-md" hideCloseButton={forced}>
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            {forced && <AlertTriangle className="w-5 h-5 text-amber-400" />}
            Change Password
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {forced 
              ? 'You must change your password before continuing. This is required for security.'
              : 'Enter your current password and choose a new one.'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-muted-foreground">Current Password</Label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-white"
              placeholder="Enter current password"
              data-testid="current-password-input"
            />
          </div>
          
          <div className="space-y-2">
            <Label className="text-muted-foreground">New Password</Label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-white"
              placeholder="Enter new password"
              data-testid="new-password-input"
            />
          </div>
          
          <div className="space-y-2">
            <Label className="text-muted-foreground">Confirm New Password</Label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-white"
              placeholder="Confirm new password"
              data-testid="confirm-password-input"
            />
          </div>
          
          <DialogFooter>
            {!forced && (
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => onOpenChange(false)} 
                className="border-zinc-700 text-muted-foreground hover:text-white"
              >
                Cancel
              </Button>
            )}
            <Button 
              type="submit" 
              disabled={isLoading}
              className="bg-blue-600 hover:bg-blue-700" 
              data-testid="change-password-submit-button"
            >
              {isLoading ? 'Changing...' : 'Change Password'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
