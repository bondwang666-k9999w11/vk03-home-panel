using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Drawing;

namespace VK03StudioRemoval {
 public sealed class ManagedFile { public string Path; public string Hash; }
 public sealed class RemovalResult { public int Removed; public int Retained; public bool DirectoryRemoved; }
 public static class Removal {
  public const string PackageId="ef41513d-174c-48d8-9ba6-9d5cc919c87f";
  public static string Hash(string path) { using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete)) using(var hash=SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant(); }
  static string Root(string path) {
   string root=System.IO.Path.GetFullPath(path).TrimEnd('\\','/');string drive=System.IO.Path.GetPathRoot(root).TrimEnd('\\','/');
   if(root.Length<=drive.Length || root.Equals(@"C:\VK03",StringComparison.OrdinalIgnoreCase) || root.StartsWith(@"C:\VK03\",StringComparison.OrdinalIgnoreCase))throw new IOException("不能卸载此目录。");
   foreach(string vendor in new[]{@"C:\Program Files (x86)\Myth.Cool",@"C:\Program Files\Myth.Cool"})if(root.Equals(vendor,StringComparison.OrdinalIgnoreCase)||root.StartsWith(vendor+"\\",StringComparison.OrdinalIgnoreCase))throw new IOException("不能卸载原厂软件目录。");
   string windows=Environment.GetFolderPath(Environment.SpecialFolder.Windows).TrimEnd('\\');
   if(root.Equals(windows,StringComparison.OrdinalIgnoreCase)||root.StartsWith(windows+"\\",StringComparison.OrdinalIgnoreCase))throw new IOException("不能卸载系统目录。");
   for(var dir=new DirectoryInfo(root);dir!=null;dir=dir.Parent)if(dir.Exists&&(dir.Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException("不支持通过链接目录卸载。");
   return root;
  }
  static void NoLink(string path,string root) {
   if(File.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new IOException("不处理链接文件。");
   for(var dir=new DirectoryInfo(System.IO.Path.GetDirectoryName(path));dir!=null&&dir.FullName.Length>=root.Length;dir=dir.Parent)if(dir.Exists&&(dir.Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException("不处理链接目录。");
  }
  public static List<ManagedFile> Plan(string input) {
   string root=Root(input);var json=new JavaScriptSerializer();json.MaxJsonLength=8*1024*1024;
   NoLink(System.IO.Path.Combine(root,"studio-package.json"),root);NoLink(System.IO.Path.Combine(root,"files.sha256.json"),root);
   var marker=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(System.IO.Path.Combine(root,"studio-package.json")));
   if(!marker.ContainsKey("packageId")||Convert.ToString(marker["packageId"])!=PackageId||!File.Exists(System.IO.Path.Combine(root,"VK03Studio.exe")))throw new IOException("此目录不是可识别的 VK03 Studio 安装。");
   var manifest=json.Deserialize<Dictionary<string,string>>(File.ReadAllText(System.IO.Path.Combine(root,"files.sha256.json")));if(manifest.Count==0||manifest.Count>5000)throw new IOException("程序清单无效。");
   var result=new List<ManagedFile>();var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(var item in manifest) {
    string name=item.Key.Replace('/', '\\');if(System.IO.Path.IsPathRooted(name)||name.Split('\\').Any(x=>x==".."||x=="."||x.Length==0||x.EndsWith(" ")||x.EndsWith("."))||name.Contains(':'))throw new IOException("程序清单路径无效。");
    string path=System.IO.Path.GetFullPath(System.IO.Path.Combine(root,name));if(!path.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase)||!seen.Add(path))throw new IOException("程序清单路径越界或重复。");
    if(item.Value==null||item.Value.Length!=64||item.Value.Any(c=>!Uri.IsHexDigit(c)))throw new IOException("程序清单校验值无效。");
    NoLink(path,root);result.Add(new ManagedFile{Path=path,Hash=item.Value});
   }
   return result;
  }
  public static RemovalResult RemoveManaged(string input) {
   string root=Root(input);var plan=Plan(root);var result=new RemovalResult();string manifest=System.IO.Path.Combine(root,"files.sha256.json");string originalHash=Hash(manifest);
   foreach(var file in plan) {
    if(!File.Exists(file.Path))continue;
    try{NoLink(file.Path,root);if(!Hash(file.Path).Equals(file.Hash,StringComparison.OrdinalIgnoreCase)){result.Retained++;continue;}File.Delete(file.Path);result.Removed++;}catch{result.Retained++;}
   }
   try{if(File.Exists(manifest)&&Hash(manifest)==originalHash)File.Delete(manifest);}catch{result.Retained++;}
   var dirs=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   foreach(var file in plan)for(string dir=System.IO.Path.GetDirectoryName(file.Path);dir!=null&&dir.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase);dir=System.IO.Path.GetDirectoryName(dir))dirs.Add(dir);
   foreach(string dir in dirs.OrderByDescending(x=>x.Length))try{if(Directory.Exists(dir)&&!Directory.EnumerateFileSystemEntries(dir).Any())Directory.Delete(dir,false);}catch{}
   try{if(!Directory.EnumerateFileSystemEntries(root).Any()){Directory.Delete(root,false);result.DirectoryRemoved=true;}}catch{}
   return result;
  }
  public static bool Running(string root) {
   foreach(var process in Process.GetProcessesByName("VK03Studio"))using(process)try{if(process.MainModule.FileName.Equals(System.IO.Path.Combine(root,"VK03Studio.exe"),StringComparison.OrdinalIgnoreCase))return true;}catch{return true;}
   return false;
  }
 }
 static class Program {
  [STAThread] static void Main(string[] args) {
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
   try{if(args.Length==1&&args[0]=="--worker"){Worker();return;}Show();}catch(Exception e){MessageBox.Show(e.Message,"VK03 Studio 卸载",MessageBoxButtons.OK,MessageBoxIcon.Warning);}
  }
  static void Show() {
   string root=System.IO.Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);Removal.Plan(root);
   var form=new Form{Text="卸载 VK03 Studio",ClientSize=new Size(510,245),StartPosition=FormStartPosition.CenterScreen,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,MinimizeBox=false,Font=new Font("Microsoft YaHei",9)};
   var title=new Label{Text="卸载 VK03 Studio",Font=new Font("Microsoft YaHei",15,FontStyle.Bold),Location=new Point(24,20),Size=new Size(455,32)};
   var detail=new Label{Text="将移除此目录内未修改的程序文件：\r\n"+root+"\r\n\r\n保留您的方案、背景素材和其他自行添加的文件。\r\n请先从系统托盘退出此版本的 VK03 Studio。",Location=new Point(24,68),Size=new Size(455,113)};
   var remove=new Button{Text="卸载",Location=new Point(294,198),Size=new Size(88,30)};var cancel=new Button{Text="取消",Location=new Point(394,198),Size=new Size(88,30),DialogResult=DialogResult.Cancel};form.CancelButton=cancel;
   remove.Click+=(sender,e)=>{
    try{
     if(Removal.Running(root)){MessageBox.Show("请先从托盘退出这个目录中的 VK03 Studio，再卸载。",form.Text);return;}
     remove.Enabled=false;Removal.Plan(root);
     string temp=System.IO.Path.Combine(System.IO.Path.GetTempPath(),"VK03Studio-Uninstall-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(temp);string helper=System.IO.Path.Combine(temp,"uninstall.exe");File.Copy(Assembly.GetExecutingAssembly().Location,helper);
     var grant=new Dictionary<string,object>{{"root",root},{"parent",Process.GetCurrentProcess().Id},{"expires",DateTime.UtcNow.AddMinutes(1).Ticks},{"manifest",Removal.Hash(System.IO.Path.Combine(root,"files.sha256.json"))},{"approved",true}};
     File.WriteAllText(System.IO.Path.Combine(temp,"grant.json"),new JavaScriptSerializer().Serialize(grant));Process.Start(new ProcessStartInfo(helper,"--worker"){UseShellExecute=false,CreateNoWindow=true});form.Close();
    }catch(Exception error){remove.Enabled=true;MessageBox.Show(error.Message,form.Text);}
   };
   form.Controls.AddRange(new Control[]{title,detail,remove,cancel});Application.Run(form);
  }
  static void Worker() {
   string own=System.IO.Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);string temp=System.IO.Path.GetTempPath().TrimEnd('\\')+"\\";
   if(!own.StartsWith(temp,StringComparison.OrdinalIgnoreCase)||!new DirectoryInfo(own).Name.StartsWith("VK03Studio-Uninstall-",StringComparison.Ordinal))throw new IOException("卸载会话无效。");
   string grantPath=System.IO.Path.Combine(own,"grant.json");var grant=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(grantPath));
   if(!Convert.ToBoolean(grant["approved"])||Convert.ToInt64(grant["expires"])<DateTime.UtcNow.Ticks)throw new IOException("卸载确认已失效，请重新打开卸载程序。");
   string root=Convert.ToString(grant["root"]);if(Removal.Hash(System.IO.Path.Combine(root,"files.sha256.json"))!=Convert.ToString(grant["manifest"]))throw new IOException("程序清单已改变，请重新确认。");
   try{using(var parent=Process.GetProcessById(Convert.ToInt32(grant["parent"])))if(!parent.WaitForExit(10000))throw new IOException("卸载窗口仍在运行，请稍后重试。");}catch(ArgumentException){}
   if(Removal.Running(root))throw new IOException("VK03 Studio 正在运行，请先退出。");File.Delete(grantPath);var result=Removal.RemoveManaged(root);
   MessageBox.Show(result.Retained==0?"卸载完成。您的方案与素材已保留。":"卸载完成。部分已修改或被占用的文件已保留，您可稍后检查程序目录。\r\n您的方案与素材已保留。","VK03 Studio",MessageBoxButtons.OK,MessageBoxIcon.Information);
  }
 }
}
