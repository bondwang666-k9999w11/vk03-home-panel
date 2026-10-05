// CPU-only read-only helper using the official LibreHardwareMonitor library.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Web.Script.Serialization;
using LibreHardwareMonitor.Hardware;

class VK03Sensors {
    static string root;
    static JavaScriptSerializer serializer = new JavaScriptSerializer();
    static double? Number(float? value) {
        if (!value.HasValue || float.IsNaN(value.Value) || float.IsInfinity(value.Value) || value.Value <= 0 || value.Value > 130) return null;
        return Math.Round(value.Value, 1);
    }
    static double? Temperature(IHardware hardware) {
        hardware.Update();
        var values = hardware.Sensors.Where(s => s.SensorType == SensorType.Temperature && Number(s.Value).HasValue).ToList();
        foreach (string name in new [] { "CPU Package", "Core (Tctl/Tdie)", "Core (Tdie)", "CPU (Tctl/Tdie)" }) {
            var sensor = values.FirstOrDefault(s => s.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
            if (sensor != null) return Number(sensor.Value);
        }
        var cores = values.Where(s => s.Name.IndexOf("Core", StringComparison.OrdinalIgnoreCase) >= 0).ToList();
        if (cores.Count > 0) return cores.Max(s => Number(s.Value));
        return null;
    }
    static void Write(double? value, string error) {
        var data = new Dictionary<string, object> {
            { "timestamp", (DateTime.UtcNow - new DateTime(1970,1,1)).TotalSeconds },
            { "cpu_temp", value }, { "error", error }, { "source", "LibreHardwareMonitor 0.9.6" }
        };
        string target = Path.Combine(root, "vk03_cpu_sensor.json");
        string temp = target + ".pending";
        File.WriteAllText(temp, serializer.Serialize(data));
        if (File.Exists(target)) File.Replace(temp,target,null); else File.Move(temp,target);
    }
    [STAThread]
    static int Main(string[] args) {
        root = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,".."));
        if (args.Length > 0 && args[0] == "--self-test") { Write(42.5,"self-test"); return 0; }
        bool created;
        using (var mutex = new Mutex(true,"Local\\VK03CpuSensors",out created)) {
            if (!created) return 0;
            string stop = Path.Combine(root,"vk03_sensors_stop.flag");
            try {
                if (File.Exists(stop)) File.Delete(stop);
                var computer = new Computer { IsCpuEnabled=true };
                try {
                    computer.Open();
                    while (!File.Exists(stop)) {
                        try {
                            double? temperature = null;
                            foreach (var hardware in computer.Hardware) {
                                if (hardware.HardwareType == HardwareType.Cpu) {
                                    var value = Temperature(hardware);
                                    if (value.HasValue) temperature = temperature.HasValue ? Math.Max(temperature.Value,value.Value) : value;
                                }
                            }
                            Write(temperature,temperature.HasValue ? "" : "CPU temperature unavailable; check PawnIO and hardware support.");
                        } catch (Exception exc) { Write(null,exc.GetType().Name); }
                        Thread.Sleep(1000);
                    }
                } finally { computer.Close(); }
            } catch (Exception exc) {
                try { Write(null,exc.GetType().Name); } catch { }
                return 1;
            }
        }
        return 0;
    }
}
