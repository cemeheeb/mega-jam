// Чёрная дыра для неба главного меню. tools/ue/build_menu.py вставляет этот текст в узел Custom материала
// /Game/Game/Menu/M_BlackHole (выход float3, свечение неосвещённого материала на сфере вокруг камеры).
//
// Входы узла:
//   InDir  — направление взгляда в мире (от камеры к пикселю);
//   InTime — время, с;
//   InHole — xyz: направление от камеры на дыру, w: расстояние до неё;
//   InDisk — x: высота камеры над плоскостью диска, градусы; y: наклон диска на экране, градусы;
//            z, w: внутренний и внешний радиусы диска;
//   InLook — x: яркость диска; y: яркость звёзд; z: скорость вращения диска; w: температура горячего места, К.
// Единица длины — радиус горизонта (rs = 1, масса M = 0,5).
//
// Как считается:
// - луч от камеры ведётся по уравнению фотонной орбиты Шварцшильда x'' = −1,5·h²·x / r⁵ (h — момент импульса),
//   шаг растёт с расстоянием (метод Верле); лучи, прошедшие далеко, гнутся по формуле слабого линзирования
//   α = (1 − cos ψ) / b, та же поправка добирает остаток изгиба после выхода луча из области дыры — шва нет;
// - тонкий диск: при каждом пересечении плоскости — свет с кеплеровым вращением узора, доплеровским усилением
//   и гравитационным красным смещением (цвет — по чёрному телу), непрозрачность по плотности узора;
//   вторичные пересечения дают дугу диска над и под тенью и фотонное кольцо;
// - над диском — светящаяся дымка, набирается вдоль луча;
// - фон по конечному направлению луча: три слоя звёзд, Млечный Путь с пылевыми прожилками, слабые туманности;
//   звёзды мерцают, как сквозь воздух: яркость — случайный шум по времени (около 7 и 17 Гц), распределена
//   логнормально (короткие вспышки и провалы), у ярких звёзд каналы шумят врозь — цветные искры.

struct FBlackHole
{
	float Hash13(float3 p)
	{
		p = frac(p * 0.1031);
		p += dot(p, p.zyx + 31.32);
		return frac((p.x + p.y) * p.z);
	}

	float3 Hash33(float3 p)
	{
		p = frac(p * float3(0.1031, 0.1030, 0.0973));
		p += dot(p, p.yxz + 33.33);
		return frac((p.xxy + p.yxx) * p.zyx);
	}

	float Noise(float3 p)
	{
		float3 i = floor(p);
		float3 f = frac(p);
		float3 u = f * f * (3.0 - 2.0 * f);
		float n000 = Hash13(i);
		float n100 = Hash13(i + float3(1, 0, 0));
		float n010 = Hash13(i + float3(0, 1, 0));
		float n110 = Hash13(i + float3(1, 1, 0));
		float n001 = Hash13(i + float3(0, 0, 1));
		float n101 = Hash13(i + float3(1, 0, 1));
		float n011 = Hash13(i + float3(0, 1, 1));
		float n111 = Hash13(i + float3(1, 1, 1));
		return lerp(lerp(lerp(n000, n100, u.x), lerp(n010, n110, u.x), u.y),
		            lerp(lerp(n001, n101, u.x), lerp(n011, n111, u.x), u.y), u.z);
	}

	// Шум по времени в [−1, 1]: значения в целых точках, гладкая склейка между ними.
	float Noise1(float x, float Seed)
	{
		float i = floor(x);
		float f = frac(x);
		float u = f * f * (3.0 - 2.0 * f);
		return lerp(Hash13(float3(i, Seed, 1.7)), Hash13(float3(i + 1.0, Seed, 1.7)), u) * 2.0 - 1.0;
	}

	// Мерцание звезды: быстрый неровный шум из двух слоёв.
	float Scint(float t, float Seed)
	{
		return 0.65 * Noise1(t * 7.0, Seed) + 0.35 * Noise1(t * 17.0, Seed + 5.3);
	}

	float Fbm(float3 p, int Octaves)
	{
		float Sum = 0.0;
		float Amp = 0.5;
		for (int i = 0; i < Octaves; i++)
		{
			Sum += Amp * Noise(p);
			p = p * 2.02 + float3(17.1, 3.7, 9.3);
			Amp *= 0.5;
		}
		return Sum;
	}

	// Цвет чёрного тела (приближение Таннера Хелланда), линейный, самый яркий канал = 1.
	float3 Blackbody(float Kelvin)
	{
		float t = clamp(Kelvin, 800.0, 40000.0) / 100.0;
		float r = t <= 66.0 ? 1.0 : 1.292936 * pow(t - 60.0, -0.1332048);
		float g = t <= 66.0 ? 0.3900816 * log(t) - 0.6318414 : 1.129891 * pow(t - 60.0, -0.0755148);
		float b = t >= 66.0 ? 1.0 : (t <= 19.0 ? 0.0 : 0.5432068 * log(t - 10.0) - 1.1962541);
		float3 c = pow(saturate(float3(r, g, b)), 2.2);
		return c / max(max(c.r, c.g), max(c.b, 1e-4));
	}

	// Слой звёзд: в каждой клетке сетки по направлению — не больше одной звезды; проверяются 8 клеток вокруг точки,
	// поэтому звезда у края клетки не обрезается. PixelSize — угловой размер пикселя, рад; T — время, с.
	float3 StarLayer(float3 d, float Scale, float Density, float PixelSize, float Seed, float Dim, float Bright, float T)
	{
		const float TwinkleAmount = 1.1;    // сила мерцания: при 1,1 яркость обычно гуляет в 0,5–2 раза
		const float TwinkleSpeed = 1.0;     // множитель частот шума (7 и 17 Гц)
		const float TwinkleColor = 0.5;     // цветные искры у ярких звёзд: 0 — нет
		float3 p = d * Scale;
		float3 Base = floor(p - 0.5);
		float3 Col = 0;
		for (int k = 0; k < 8; k++)
		{
			float3 Id = Base + float3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
			float3 h = Hash33(Id + Seed);
			if (h.x < Density)
			{
				float3 Pos = Id + 0.15 + 0.7 * Hash33(Id * 1.37 + Seed + 7.0);
				float3 Delta = p - normalize(Pos) * Scale;
				float Mag = pow(h.y, 8.0);                              // яркие звёзды редки
				float Radius = PixelSize * Scale * (0.7 + 1.3 * Mag);
				float Core = exp(-dot(Delta, Delta) / (Radius * Radius));
				float3 Tint = h.z < 0.22 ? float3(1.0, 0.70, 0.46) : (h.z < 0.8 ? float3(1.0, 0.95, 0.90) : float3(0.66, 0.79, 1.0));
				float3 h2 = Hash33(Id * 2.71 + Seed + 3.0);
				float Sd = h2.x * 97.0 + h2.y * 13.0;
				float Ts = T * TwinkleSpeed + h2.z * 50.0;
				float Gm = Scint(Ts, Sd);
				float3 Gc = float3(Scint(Ts * 1.13, Sd + 31.7), Gm, Scint(Ts * 0.91, Sd + 63.1));
				float3 G = lerp(Gm.xxx, Gc, TwinkleColor * saturate(0.2 + 3.0 * Mag));
				float3 Twinkle = exp(TwinkleAmount * G - 0.08 * TwinkleAmount * TwinkleAmount);
				Col += Tint * Core * (Dim + Bright * Mag) * Twinkle;
			}
		}
		return Col;
	}

	// Млечный Путь: яркая полоса с облаками и тёмными пылевыми прожилками, тёплое ядро. Band — сила полосы.
	float3 Galaxy(float3 d, out float Band)
	{
		const float3 Pole = normalize(float3(0.10, -0.52, 0.85));
		const float3 Core = normalize(float3(0.82, -0.52, -0.05) - Pole * dot(float3(0.82, -0.52, -0.05), Pole));
		float Lat = dot(d, Pole);
		Band = exp(-Lat * Lat / 0.006);
		float Halo = exp(-Lat * Lat / 0.05);
		float Bulge = pow(saturate(dot(d, Core)), 6.0);
		float Clouds = Fbm(d * 5.0 + float3(3.1, 7.7, 1.3), 5);
		float Grain = Fbm(d * 23.0 + Clouds * 1.5, 4);
		float Dust = smoothstep(0.45, 0.70, Fbm(d * 9.0 + float3(8.3, 1.1, 4.4) + Clouds * 0.8, 5)) * exp(-Lat * Lat / 0.0045);
		float Light = Band * (0.15 + 1.2 * Clouds * Grain) * (1.0 + 3.0 * Bulge) + Halo * 0.03 * (1.0 + 4.0 * Bulge);
		float3 Col = lerp(float3(0.52, 0.66, 1.0), float3(1.0, 0.80, 0.58), saturate(Bulge * 1.6 + 0.15));
		return Col * Light * (1.0 - 0.9 * Dust) * 0.14;
	}

	// Слабые туманности в палитре корабля: бирюзовая, тлеющая оранжевая, фиолетовая тень.
	float3 Nebula(float3 d)
	{
		float a = Fbm(d * 2.3 + float3(5.2, 1.3, 8.8), 5);
		float b = Fbm(d * 4.1 + float3(2.7, 9.1, 3.3) + a * 1.2, 4);
		float3 Col = float3(0.10, 0.42, 0.50) * smoothstep(0.48, 0.85, a)
		           + float3(0.65, 0.22, 0.07) * smoothstep(0.55, 0.90, b) * 0.7
		           + float3(0.22, 0.10, 0.40) * smoothstep(0.35, 0.75, a * b * 2.0) * 0.5;
		return Col * 0.03;
	}

	float3 Sky(float3 d, float StarGain, float T)
	{
		float Band;
		float3 Milky = Galaxy(d, Band);
		float3 Stars = StarLayer(d, 40.0, 0.10, 0.0006, 1.0, 0.05, 6.0, T)
		             + StarLayer(d, 110.0, 0.18, 0.0006, 2.0, 0.025, 1.2, T)
		             + StarLayer(d, 300.0, 0.04 + 0.5 * Band, 0.0006, 3.0, 0.012, 0.25, T);
		return Stars * StarGain + Milky + Nebula(d);
	}

	// Плотность узора диска: газовые облака, вытянутые вдоль орбиты (угловая частота низкая, радиальная высокая),
	// поверх — тонкие волокна; угол слегка искривлён самими облаками, чтобы волокна не шли ровными кольцами.
	float DiskDensity(float Ang, float Lr, float Seed)
	{
		float2 Cs = float2(cos(Ang), sin(Ang));
		float Big = Fbm(float3(Cs * 1.8, Lr * 5.0 + Seed), 5);
		float A2 = Ang + (Big - 0.5) * 0.9;
		float2 Cw = float2(cos(A2), sin(A2));
		float Fibers = Fbm(float3(Cw * 3.2, Lr * 26.0 + Seed + Big * 3.0), 4);
		float Fine = Noise(float3(Cw * 9.0, Lr * 70.0 + Seed));
		float D = Big * 0.75 + Fibers * 0.65 + Fine * 0.15 - 0.42;
		return smoothstep(0.05, 0.75, D);
	}

	// Температурный профиль тонкого диска: x^−3/4 · (1 − x^−1/2)^1/4, максимум = 1 около x = 1,36.
	float Profile(float x)
	{
		return pow(x, -0.75) * pow(saturate(1.0 - rsqrt(x)), 0.25) / 0.488;
	}

	// Свет диска в точке пересечения: rgb — излучение, a — непрозрачность. RayDir — направление хода луча от камеры.
	float4 DiskSample(float3 Pc, float3 RayDir, float3 N, float3 E1, float3 E2, float Rin, float Rout, float T, float4 Look)
	{
		float r = length(Pc);
		if (r < Rin * 0.9 || r > Rout * 1.05)
		{
			return 0;
		}
		float x = r / Rin;
		float Phi = atan2(dot(Pc, E2), dot(Pc, E1));
		float Omega = sqrt(0.5 / (r * r * r));                  // кеплерово вращение
		// два слоя со сдвигом фазы: дифференциальное вращение не закручивает узор бесконечно
		float Tt = T * 4.6 * Look.z;
		const float Period = 40.0;
		float Ph0 = frac(Tt / Period);
		float Ph1 = frac(Tt / Period + 0.5);
		float W0 = 1.0 - abs(2.0 * Ph0 - 1.0);
		float Lr = log(r);
		float Dens = lerp(DiskDensity(Phi - Omega * Ph1 * Period, Lr, 31.7),
		                  DiskDensity(Phi - Omega * Ph0 * Period, Lr, 0.0), W0);
		float Inner = smoothstep(Rin * 0.9, Rin * 1.2, r);
		float Outer = 1.0 - smoothstep(Rout * 0.55, Rout * 1.02, r);
		float Alpha = saturate((0.25 + Dens * 2.2) * (1.0 + 2.5 * exp(-(x - 1.0) * 2.5))) * Inner * Outer;

		float Prof = Profile(x);
		float3 VDir = normalize(cross(N, Pc));                  // скорость вещества диска
		float Beta = min(sqrt(0.5 / max(r - 1.0, 0.6)), 0.85);
		float Gamma = rsqrt(1.0 - Beta * Beta);
		float CosA = dot(VDir, -RayDir);                         // свет идёт к камере против хода луча
		float G = sqrt(saturate(1.0 - 1.0 / r)) / (Gamma * (1.0 - Beta * CosA));
		float3 Col = Blackbody(Look.w * Prof * G);
		// у внутреннего края — раскалённая добела кромка
		float Rim = exp(-(x - 1.0) * 6.0) * 1.5;
		float I = Look.x * (pow(Prof, 2.2) + Rim) * pow(G, 3.5) * (0.3 + 0.7 * Dens);
		return float4(Col * I, Alpha);
	}

	// Светящаяся дымка над и под диском (на единицу длины луча).
	float3 Haze(float3 P, float3 N, float Rin, float Rout, float4 Look)
	{
		float h = dot(P, N);
		float Rp = length(P - N * h);
		float Thick = 0.10 + 0.05 * Rp;
		float Shape = exp(-abs(h) / Thick) * smoothstep(Rin * 0.7, Rin * 1.4, Rp) * (1.0 - smoothstep(Rout * 0.35, Rout, Rp));
		float Prof = Profile(max(Rp / Rin, 1.0001));
		float3 Col = lerp(float3(1.0, 0.42, 0.14), float3(1.0, 0.84, 0.68), saturate(Prof));
		return Col * Shape * Prof * Prof * Look.x * 0.035;
	}

	// Остаток изгиба для луча, уходящего из точки P прямо (слабое линзирование): α = (1 − cos ψ) / b к дыре.
	float3 WeakBend(float3 P, float3 V)
	{
		float3 Lm = cross(P, V);
		float B = max(length(Lm), 1e-3);
		float3 Closest = P - V * dot(P, V);
		float CosPsi = dot(V, normalize(P));
		return normalize(V - normalize(Closest) * (1.0 - CosPsi) / B);
	}

	float3 Render(float3 InDir, float T, float4 Hole, float4 Disk, float4 Look)
	{
		float3 Dir = normalize(InDir);
		float3 F = normalize(Hole.xyz);
		float Dist = Hole.w;
		float3 Up0 = abs(F.z) < 0.98 ? float3(0, 0, 1) : float3(1, 0, 0);
		float3 Right = normalize(cross(Up0, F));
		float3 Up = cross(F, Right);
		float Elev = radians(Disk.x);
		float Roll = radians(Disk.y);
		float3 UpR = Up * cos(Roll) + Right * sin(Roll);
		float3 N = normalize(UpR * cos(Elev) - F * sin(Elev));  // нормаль диска: камера над плоскостью на Elev
		float3 E1 = normalize(cross(N, F));
		float3 E2 = cross(N, E1);
		float Rin = Disk.z;
		float Rout = Disk.w;

		float3 P = -F * Dist;
		float3 V = Dir;
		float H2 = dot(cross(P, V), cross(P, V));
		// луч проходит далеко: диска и дымки на пути нет, только изгиб
		if (H2 > Rout * Rout * 2.6)
		{
			return Sky(WeakBend(P, V), Look.y, T);
		}

		float3 Acc = 0;
		float A = 0;
		bool Captured = false;
		bool Escaped = false;
		// сдвиг первого шага на случайную долю (меняется от кадра к кадру): полосы дымки уходят в шум, сглаживание его съедает
		float Jitter = Hash13(float3(Dir.xy * 4096.0, frac(T * 7.13) * 512.0));
		bool First = true;
		[loop]
		for (int i = 0; i < 320; i++)
		{
			float R2 = dot(P, P);
			float R = sqrt(R2);
			if (R < 1.0)
			{
				Captured = true;
				break;
			}
			if (R > Rout * 1.1 && dot(P, V) > 0.0)
			{
				Escaped = true;
				break;
			}
			float Dt = clamp(0.035 * R, 0.012, 2.0);
			if (First)
			{
				Dt *= Jitter + 0.05;
				First = false;
			}
			float3 Acl = -1.5 * H2 * P / (R2 * R2 * R);
			float3 Pn = P + V * Dt + 0.5 * Acl * Dt * Dt;
			float R2n = dot(Pn, Pn);
			float Rn = sqrt(R2n);
			float3 Acn = -1.5 * H2 * Pn / (R2n * R2n * Rn);
			float3 Vn = V + 0.5 * (Acl + Acn) * Dt;

			float S0 = dot(P, N);
			float S1 = dot(Pn, N);
			if (S0 * S1 < 0.0 && A < 0.995)
			{
				float K = S0 / (S0 - S1);
				float4 Dc = DiskSample(lerp(P, Pn, K), normalize(lerp(V, Vn, K)), N, E1, E2, Rin, Rout, T, Look);
				Acc += (1.0 - A) * Dc.rgb * Dc.a;
				A += (1.0 - A) * Dc.a;
			}
			Acc += (1.0 - A) * Haze(0.5 * (P + Pn), N, Rin, Rout, Look) * Dt;
			P = Pn;
			V = Vn;
		}
		float3 Back = 0;
		if (Escaped || (!Captured && length(P) > 3.0))
		{
			Back = Sky(WeakBend(P, normalize(V)), Look.y, T);
		}
		return Acc + (1.0 - A) * Back;
	}
};

FBlackHole BH;
return BH.Render(InDir, InTime, InHole, InDisk, InLook);
