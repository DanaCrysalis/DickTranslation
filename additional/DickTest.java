import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;

class DickTest {

    public static void main(String[] args) throws IOException {
        
        String input = "D:\\emulation\\dos\\DickTranslation\\DICK.DAT.new";
        String output = "D:\\emulation\\dos\\games\\DICK\\DICK.DAT";
        
		System.out.printf("Input: %s%n", input);
		System.out.printf("Output: %s%n", output);
		
        byte[] bytes = Files.readAllBytes(new File(input).toPath());

        // offsets found by searching bytes: 66 81 2E EC 26 E4 00 00 00 66 81 06 EC 26 C0 17
        int[] offsetsE417C0 = {0x11D366,
                0x226C8C,
                0x2C8ADC,
                0x36AC8C,
                0x37A5F3,
                0x4A96CF,
                0x578FBF,
                0x6900CE,
                0x7CB286,
                0x854DBC,
                0x9E761C,
                0xA78132,
                0xB05A74,
                0xBBA062,
                0xD08D71,
                0x101347E,
                0x1163991,
                0x1183411,
                0x12B1857,
                0x1335054,
                0x13D7329,
                0x146446F,
                0x150F9C8,
                0x15FB87A,
                0x167AE71,
                0x17101A8,
                0x19D2D0D,
                0x1A14143,
                0x1BE1676,
                0x1C00C91,
                0x1C3147C,
                0x1D8EB5D,
                0x1F935C4,
                0x20615C8,
                0x22148E0,
                0x2244456,
                0x2405C1E,
                0x250919A,
                0x273ACD3,
                0x27C4214,
                0x27E47FE,
                0x29A0217,
                0x2A3B02B,
                0x2B966ED,
                0x2C3F8C3,
                0x2CFB364,
                0x2D78DA7,
                0x2E2200A,
                0x2E4248B,
                0x2F9B7DF,
                0x2FBBCB4,
                0x30C465C,
                0x30E4BF1,
                0x32150CB,
                0x3235699,
                0x3365B9B,
                0x3386171,
                0x3496D5C,
                0x34B8769,
                0x35D0979,
                0x3714644,
                0x3873E8D,
                0x38A44DE,
                0x38C4357,
                0x38E4943,
                0x39049DD,
                0x3924E9B,
                0x3944F33,
                0x3964F08,
                0x3F5067D,
                0x40293C1,
                0x40EFAD5,
                0x41E1242,
                0x434CBD8,
                0x43AB8BE,
                0x43CBAEB,
                0x44430E9,
                0x4528836,
                0x46425F0,
                0x46BCE28,
                0x4743FF1,
                0x484DB5D,
                0x48C7DEA,
                0x4AEE03E,
                0x4E0CA55,
                0x4F43688,
                0x5279A35,
                0x52FCAFC,
                0x54A11A1};

        //offsets found by searching bytes: 66 83 06 EC 26 13 66 81 3E EC 26 12 C9 0A 00
        int[] offsets13AC912 = {
                0x11D2BE,
                0x226BE4,
                0x2C8A34,
                0x36ABE4,
                0x37A54B,
                0x4A9627,
                0x578F17,
                0x690026,
                0x7CB1DE,
                0x854D14,
                0x9E7574,
                0xA7808A,
                0xB059CC,
                0xBB9FBA,
                0xD08CC9,
                0x10133D6,
                0x11638E9,
                0x1183369,
                0x12B17AF,
                0x1334FAC,
                0x13D7281,
                0x14643C7,
                0x150F920,
                0x15FB7D2,
                0x167ADC9,
                0x1710100,
                0x19D2C65,
                0x1A1409B,
                0x1BE15CE,
                0x1C00BE9,
                0x1C313D4,
                0x1D8EAB5,
                0x1F9351C,
                0x2061520,
                0x2214838,
                0x22443AE,
                0x2405B76,
                0x25090F2,
                0x273AC2B,
                0x27C416C,
                0x27E4756,
                0x29A016F,
                0x2A3AF83,
                0x2B96645,
                0x2C3F81B,
                0x2CFB2BC,
                0x2D78CFF,
                0x2E21F62,
                0x2E423E3,
                0x2F9B737,
                0x2FBBC0C,
                0x30C45B4,
                0x30E4B49,
                0x3215023,
                0x32355F1,
                0x3365AF3,
                0x33860C9,
                0x3496CB4,
                0x34B86C1,
                0x35D08D1,
                0x371459C,
                0x3873DE5,
                0x38A4436,
                0x38C42AF,
                0x38E489B,
                0x3904935,
                0x3924DF3,
                0x3944E8B,
                0x3964E60,
                0x4029319,
                0x40EFA2D,
                0x41E119A,
                0x434CB30,
                0x43AB816,
                0x43CBA43,
                0x4443041,
                0x452878E,
                0x4642548,
                0x46BCD80,
                0x4743F49,
                0x484DAB5,
                0x48C7D42,
                0x4AEDF96,
                0x4E0C9AD,
                0x4F435E0,
                0x527998D,
                0x54A10F9
        };


        for (int i : offsetsE417C0) {
            writeByteArrayToArray(parseHex("0E"), bytes, i-8); // replaces 0C
            writeByteArrayToArray(parseHex("E0"), bytes, i+5); // replaces E4
            writeByteArrayToArray(parseHex("C0 17"), bytes, i+14); // replaces 17C0
        }


        for (int i : offsets13AC912) {
            writeByteArrayToArray(parseHex("10"), bytes, i+5); // replaces 13
            writeByteArrayToArray(parseHex("0E C9 0A 00"), bytes, i+11); // replaces 000A9C12
        }


        // BUY MENU DEF
        // searched for: 01 00 88 03 05 92 02 00 82 03 12 05 C5 A9 01 00 8E 04 96 96 01 00 88 03 56 AE 02 00 82 03 12 05 7F B2 02 00 AD 04 7C 01 3F CA 02 00 AA 03 7A 06 79 B2
        // length: 0x32 bytes
        // found: 88
        int[] offsetsBuy = {
                0x10955C,
                0x212EDE,
                0x2B5402,
                0x34675A,
                0x35679C,
                0x386999,
                0x4B5988,
                0x58567E,
                0x69C302,
                0x7D71BE,
                0x860F95,
                0x9F3C5B,
                0xA843DC,
                0xB121F4,
                0xBC6221,
                0xD150AF,
                0x101FC8F,
                0x116F565,
                0x118F763,
                0x12BDAB0,
                0x134138C,
                0x13E3819,
                0x1470AFF,
                0x151C18B,
                0x1607BA9,
                0x1685529,
                0x171C129,
                0x19DFC4E,
                0x1A208D2,
                0x1BED237,
                0x1C0D435,
                0x1C3D633,
                0x1D9B335,
                0x1EACB46,
                0x1F9F8E5,
                0x206DDC4,
                0x2220AB8,
                0x2250CB6,
                0x2412303,
                0x25153BD,
                0x27474EC,
                0x27D0935,
                0x27F0B33,
                0x29AC5C7,
                0x2A46C90,
                0x2BA2E7D,
                0x2C4BE51,
                0x2D07847,
                0x2D855DC,
                0x2E2E78A,
                0x2E4E988,
                0x2FA7F8E,
                0x2FC818C,
                0x30D0E10,
                0x30F100E,
                0x32218A9,
                0x3241AA7,
                0x3372342,
                0x3392540,
                0x34A357A,
                0x34C4B78,
                0x35DD0F3,
                0x37202EC,
                0x3880606,
                0x38B0B04,
                0x38D0D02,
                0x38F0F00,
                0x39110FE,
                0x39312FC,
                0x39514FA,
                0x3F61A23,
                0x40361EF,
                0x40FC1C9,
                0x41ED927,
                0x435936E,
                0x43B806D,
                0x43D826B,
                0x444F30B,
                0x4534D78,
                0x464ED4A,
                0x46C944F,
                0x47504EF,
                0x485A50F,
                0x4AFABFF,
                0x4E19BA0,
                0x4F506CF,
                0x5285C2F,
                0x530EA9A,
                0x54ADD3A
        };

        for (int i : offsetsBuy) {
            writeByteArrayToArray(parseHex(
                    "D4 97 00 00 45 7A " +
                            "01 00 64 04 05 92 " +                  // "OK"
                            //"02 00 63 04 66 00 45 7A " +          // "No  "
                            "01 00 63 04 45 7A " +                  // "No"
                            "01 00 74 01 05 92 " +
                            // "02 00 63 04 66 00 45 7A " +         // "No  "
                            "01 00 63 04 45 7A " +                  // "No"
                            "02 00 86 04 CF 06 05 92 " +            // "Rest"
                            "03 00 1F 04 E0 04 7C 01 45 7A " +      // "Leave "
                            //"01 00 88 03 05 92 " +                // "Bu"
                            "02 00 88 03 CC 01 05 92 " +            // "Buy "       y  == 1CC (to be replaced with proper value)
                            "02 00 82 03 12 05 C5 A9 " +            // "Back"
                            //"01 00 8E 04 96 96 01 00 88 " +       // "Se"
                            "02 00 8E 04 F9 05 96 96 " +            // "Sell"       ll == 5F9 (to be replaced with proper value)
                            "01 00 88 03 56 AE " +
                            "02 00 82 03 12 05 7F B2 " +
                            "02 00 AD 04 7C 01 3F CA " +
                            "02 00 AA 03 7A 06 79 B2"
            ), bytes, i);
        }

        int[] offsetsBuyMenuCode = {
                0x1215B8,
                0x22AEDE,
                0x2CCD2E,
                0x37E845,
                0x4AD921,
                0x57D211,
                0x694320,
                0x7CF4D8,
                0x85900E,
                0x9EB86E,
                0xA7C384,
                0xB09CC6,
                0xBBE2B4,
                0xD0CFC3,
                0x10176D0,
                0x1187663,
                0x12B5AA9,
                0x13379E6,
                0x13DB57B,
                0x14686C1,
                0x1513C1A,
                0x15FFACC,
                0x167D5B8,
                0x17143FA,
                0x19D6F5F,
                0x1A18395,
                0x1C04EE3,
                0x1C356CE,
                0x1D92DAF,
                0x1F97816,
                0x206581A,
                0x2218B32,
                0x22486A8,
                0x2409E70,
                0x250D3EC,
                0x273EF25,
                0x27C8466,
                0x27E8A50,
                0x29A4469,
                0x2B9A93F,
                0x2C43B15,
                0x2CFF5B6,
                0x2D7CFF9,
                0x2E2625C,
                0x2E466DD,
                0x2F9FA31,
                0x2FBFF06,
                0x30C88AE,
                0x30E8E43,
                0x321931D,
                0x32398EB,
                0x3369DED,
                0x338A3C3,
                0x349AFAE,
                0x34BC9BB,
                0x35D4BCB,
                0x38780DF,
                0x38A8730,
                0x38C85A9,
                0x38E8B95,
                0x3908C2F,
                0x39290ED,
                0x3949185,
                0x3969123,
                0x3F57965,
                0x402D613,
                0x40F3D27,
                0x41E5494,
                0x4350E2A,
                0x43AFB10,
                0x43CFD3D,
                0x444733B,
                0x452CA88,
                0x4646842,
                0x46C107A,
                0x4748243,
                0x4851DAF,
                0x48CC005,
                0x4AF2290,
                0x4E10C70,
                0x4F478DA,
                0x527DC87,
                0x5303DE4,
                0x54A53F3
        };

        for (int i : offsetsBuyMenuCode) {
            int offset2D86 = i + 0x1C; // -2
            int offset2D94 = i + 0x05; // -4
            int offset2DA6 = i + 0x0F; // -4
            bytes[offset2D86] -= 2;
            bytes[offset2D94] -= 4;
            bytes[offset2DA6] -= 4;
        }


        writeByteArrayToFile(bytes, output);
    }

    public static void writeByteArrayToFile(byte[] array, String file) throws IOException {
        FileOutputStream stream = null;
        stream = new FileOutputStream(file);
        stream.write(array);
        stream.close();
    }

    public static void writeByteArrayToArray(byte[] source, byte[] target , int offset) {
        System.arraycopy(source, 0, target, offset, source.length);
    }

    public static byte[] parseHex(String hexValues) {
        String[] s1 = hexValues.split(" ");
        byte[] bytes = new byte[s1.length];

        for(int i = 0; i < s1.length; ++i) {
            bytes[i] = (byte)(Integer.parseInt(s1[i], 16) & 255);
        }

        return bytes;
    }
}