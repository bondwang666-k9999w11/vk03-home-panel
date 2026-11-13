using System;
using System.Runtime.InteropServices;
namespace VK03RE {
 [ComImport,Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class Enumerator {}
 [ComImport,Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface IEnumerator {
  [PreserveSig]int EnumAudioEndpoints(int flow,int mask,out IntPtr collection);
  [PreserveSig]int GetDefaultAudioEndpoint(int flow,int role,out IDevice device);
 }
 [ComImport,Guid("D666063F-1587-4E43-81F1-B948E807363F"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface IDevice {
  [PreserveSig]int Activate(ref Guid iid,int context,IntPtr parameters,[MarshalAs(UnmanagedType.IUnknown)]out object value);
 }
 [ComImport,Guid("5CDF2C82-841E-4546-9722-0CF74078229A"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface IVolume {
  [PreserveSig]int RegisterControlChangeNotify(IntPtr callback);
  [PreserveSig]int UnregisterControlChangeNotify(IntPtr callback);
  [PreserveSig]int GetChannelCount(out uint channels);
  [PreserveSig]int SetMasterVolumeLevel(float level,IntPtr context);
  [PreserveSig]int SetMasterVolumeLevelScalar(float level,IntPtr context);
  [PreserveSig]int GetMasterVolumeLevel(out float level);
  [PreserveSig]int GetMasterVolumeLevelScalar(out float level);
  [PreserveSig]int SetChannelVolumeLevel(uint channel,float level,IntPtr context);
  [PreserveSig]int SetChannelVolumeLevelScalar(uint channel,float level,IntPtr context);
  [PreserveSig]int GetChannelVolumeLevel(uint channel,out float level);
  [PreserveSig]int GetChannelVolumeLevelScalar(uint channel,out float level);
  [PreserveSig]int SetMute([MarshalAs(UnmanagedType.Bool)]bool mute,IntPtr context);
  [PreserveSig]int GetMute([MarshalAs(UnmanagedType.Bool)]out bool mute);
 }
 public static class Audio {
  static T Endpoint<T>(Func<IVolume,T> action) {
   object enumerator=null,endpoint=null,volume=null;
   try {
    enumerator=new Enumerator(); IDevice device;
    Marshal.ThrowExceptionForHR(((IEnumerator)enumerator).GetDefaultAudioEndpoint(0,1,out device));endpoint=device;
    Guid iid=new Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
    Marshal.ThrowExceptionForHR(device.Activate(ref iid,23,IntPtr.Zero,out volume));
    return action((IVolume)volume);
   } finally {
    if(volume!=null)Marshal.ReleaseComObject(volume);
    if(endpoint!=null)Marshal.ReleaseComObject(endpoint);
    if(enumerator!=null)Marshal.ReleaseComObject(enumerator);
   }
  }
  public static bool GetMute(){return Endpoint<bool>(delegate(IVolume v){bool muted;Marshal.ThrowExceptionForHR(v.GetMute(out muted));return muted;});}
  public static bool ToggleMute(){return Endpoint<bool>(delegate(IVolume v){bool muted;Marshal.ThrowExceptionForHR(v.GetMute(out muted));Marshal.ThrowExceptionForHR(v.SetMute(!muted,IntPtr.Zero));Marshal.ThrowExceptionForHR(v.GetMute(out muted));return muted;});}
  public static double GetVolume(){return Endpoint<double>(delegate(IVolume v){float level;Marshal.ThrowExceptionForHR(v.GetMasterVolumeLevelScalar(out level));return Math.Round(level*100,2);});}
  public static double SetVolume(double value){
   if(double.IsNaN(value)||double.IsInfinity(value)||value<0||value>100)throw new ArgumentOutOfRangeException("value");
   return Endpoint<double>(delegate(IVolume v){Marshal.ThrowExceptionForHR(v.SetMasterVolumeLevelScalar((float)(value/100),IntPtr.Zero));float actual;Marshal.ThrowExceptionForHR(v.GetMasterVolumeLevelScalar(out actual));return Math.Round(actual*100,2);});
  }
 }
}
