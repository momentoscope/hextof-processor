
#include <boost/python/module.hpp>
#include <boost/python/def.hpp>
#include <boost/python.hpp>
#include <boost/python/suite/indexing/vector_indexing_suite.hpp>

// #include <numpy/ndarrayobject.h>
namespace bp = boost::python;

#define CONVOLV_PRECISION 4.0

double dsgn(double x, std::vector<double>& p) {

	int j,n_c;
	double r,xx,x1,r_an,r_ad,r_gg,r_a1,r_sg,r_st,r_su,r_bb,r_ft,r_ai,r_um;


			r_gg=p[4]/2.35482;
			r_sg=2*r_gg*r_gg;
			r_ai=p[3]*1.5708;
			r_um=1-p[3];
			if(p[2]<p[4])
				r_st=0.2*p[2];
			else
				r_st=0.2*p[4];
			r_a1=CONVOLV_PRECISION*r_gg;
			n_c=ceil(2*r_a1/r_st);
			n_c+=2- (n_c % 2);
			x1=-r_a1;
			r_su=0;
			for(j=1;j<=n_c;j+=1) {
				r_bb=0;

				xx=2*(x-p[6]-x1)/p[2];
				r_an=cos(r_ai+r_um*atan(xx));
				r_ad=cos(r_ai)*pow((xx*xx+1),(r_um*.5));
				r_bb=r_an/r_ad*fabs(p[5]);

				r_bb*=exp(-x1*x1/r_sg);
				if ((j==1) + (j==n_c))
					r_ft=1;
				else
					r_ft=2*(j % 2)+2;
				r_su+=r_ft*r_bb;
				x1+=r_st;

			r = r_su*r_st/(7.51988*r_gg)+p[0]+p[1]*(x-p[6]);
	}

	return r;
}

double dsgnmBad2(double x, std::vector<double>& p)
{
	int np,j,k,n_c,n_k,n_ah;
	double r,xx,x1,r_an,r_ad,r_gg,r_a1,r_sg,r_st,r_su,r_sum,r_bb,r_ft,r_ai,r_um;

			np=p.size();
			n_k=(np-2)/5+1;
			r_sum=0;
			k=n_k;
			for(k=k-1;k>0;k--) {
				n_ah=5*k;
				r_gg=p[-1+n_ah]/2.35482;
				r_sg=2*r_gg*r_gg;
				r_ai=p[-2+n_ah]*1.5708;
				r_um=1-p[-2+n_ah];
				if(p[-3+n_ah]<p[-1+n_ah])
					r_st=0.2*p[-3+n_ah];
				else
					r_st=0.2*p[-1+n_ah];
				r_a1=CONVOLV_PRECISION*r_gg;
				n_c=ceil(2*r_a1/r_st);
				n_c+=2- (n_c % 2);
				x1=-r_a1;
				r_su=0;
				for(j=1;j<=n_c;j+=1) {
					r_bb=0;

					xx=2*(x-p[1+n_ah]-x1)/p[-3+n_ah];
					r_an=cos(r_ai+r_um*atan(xx));
					r_ad=cos(r_ai)*pow((xx*xx+1),(r_um*.5));
					r_bb=r_an/r_ad*fabs(p[n_ah]);

					r_bb*=exp(-x1*x1/r_sg);
					if ((j==1) + (j==n_c))
						r_ft=1;
					else
						r_ft=2*(j % 2)+2;
					r_su+=r_ft*r_bb;
					x1+=r_st;
				}
				r_sum+=r_su*r_st/(7.51988*r_gg);
			}
			r = r_sum+p[0]+p[1]*(x-p[6]);


	return r;
}

double dsgnmEad2(double x, std::vector<double>& p)
{
	int np,j,k,n_c,n_k,n_ah;
	double r,xx,x1,r_an,r_ad,r_gg,r_a1,r_sg,r_st,r_su,r_sum,r_bb,r_ft,r_ai,r_um;

			np=p.size();


			n_k=(np-2)/5+1;
			r_sum=0;

            r_gg=p[4]/2.35482;
            r_sg=2*r_gg*r_gg;
            r_ai=p[3]*1.5708;
            r_um=1-p[3];
            if(p[2]<p[4])
                r_st=0.2*p[2];
            else
                r_st=0.2*p[4];
            r_a1=CONVOLV_PRECISION*r_gg;
            n_c=ceil(2*r_a1/r_st);
            n_c+=2- (n_c % 2);
            x1=-r_a1;
            r_su=0;
            for(j=1;j<=n_c;j+=1) {
                r_bb=0;

                xx=2*(x-p[6]-x1)/p[2];
                r_an=cos(r_ai+r_um*atan(xx));
                r_ad=cos(r_ai)*pow((xx*xx+1),(r_um*.5));
                r_bb=r_an/r_ad*fabs(p[5]);

                r_bb*=exp(-x1*x1/r_sg);
                if ((j==1) + (j==n_c))
                    r_ft=1;
                else
                    r_ft=2*(j % 2)+2;
                r_su+=r_ft*r_bb;
                x1+=r_st;
            }
            r_sum+=r_su*r_st/(7.51988*r_gg);

			k=n_k;
			for(k=k-1;k>1;k--) {
				n_ah=5*k;
				r_gg=p[-1+n_ah]/2.35482;
				r_sg=2*r_gg*r_gg;
				r_ai=p[-2+n_ah]*1.5708;
				r_um=1-p[-2+n_ah];
				if(p[-3+n_ah]<p[-1+n_ah])
					r_st=0.2*p[-3+n_ah];
				else
					r_st=0.2*p[-1+n_ah];
				r_a1=CONVOLV_PRECISION*r_gg;
				n_c=ceil(2*r_a1/r_st);
				n_c+=2- (n_c % 2);
				x1=-r_a1;
				r_su=0;
				for(j=1;j<=n_c;j+=1) {
					r_bb=0;

					xx=2*(x-p[6]+p[1+n_ah]-x1)/p[-3+n_ah];
					r_an=cos(r_ai+r_um*atan(xx));
					r_ad=cos(r_ai)*pow((xx*xx+1),(r_um*.5));
					r_bb=r_an/r_ad*fabs(p[n_ah]);

					r_bb*=exp(-x1*x1/r_sg);
					if ((j==1) + (j==n_c))
						r_ft=1;
					else
						r_ft=2*(j % 2)+2;
					r_su+=r_ft*r_bb;
					x1+=r_st;
				}
				r_sum+=r_su*r_st/(7.51988*r_gg);
			}
			r = r_sum+p[0]+p[1]*(x-p[6]);



	return r;
}



BOOST_PYTHON_MODULE(XPSdoniachs_ext)
{
    using namespace boost::python;

    def("dsgnmBad2", dsgnmBad2);
    def("dsgnmEad2", dsgnmEad2);
    def("dsgn", dsgn);


    class_<std::vector<double> > ("VectorOfDouble")
        .def(vector_indexing_suite<std::vector<double> > ());
}


